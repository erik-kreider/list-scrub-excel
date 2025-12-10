import hashlib
import logging
import pickle
import re
import time
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from thefuzz import fuzz

from . import data_io, normalization
from .settings import Settings

logger = logging.getLogger(__name__)


class AccountScrubber:
    """Handles the account scrubbing workflow."""

    def __init__(self, settings: Settings, filename: str):
        self.settings = settings
        self.paths = settings.paths
        self.thresholds = settings.thresholds
        self.weights = settings.weights
        self.penalties = settings.penalties

        self.filename = filename
        self.input_path = self.paths.input_directory / f"{filename}.xlsx"
        self.output_path = self.paths.output_directory / f"{filename}_OUTPUT.xlsx"
        self.manual_review_path = self.paths.output_directory / f"{filename}_MANUAL_REVIEW.xlsx"
        self.cache_dir = self.paths.output_directory / "_cache"

    def _strip_generic_facility_tokens(self, value: str) -> str:
        tokens = {
            "hospital", "clinic", "center", "centre", "rehab", "rehabilitation",
            "care", "nursing", "facility", "facilities", "health", "healthcare",
        }
        if not value:
            return ""
        parts = [p for p in re.split(r"\s+", value) if p and p not in tokens]
        return " ".join(parts)

    def _score_candidate(self, scrub_row, db_row):
        score, details = 0, []

        penalty = float(self.penalties.location_mismatch_penalty)
        website_penalty = float(self.penalties.conflicting_website_penalty)

        scrub_country = scrub_row.get("country", "")
        db_country = db_row.get("country", "")
        if scrub_country and db_country and scrub_country != db_country:
            score -= penalty
            details.append(f"CountryMismatch(-{penalty:.0f})")

        scrub_state = scrub_row.get("state", "")
        db_state = db_row.get("state", "")
        if scrub_state and db_state and scrub_state != db_state:
            score -= penalty
            details.append(f"StateMismatch(-{penalty:.0f})")

        name_sim = fuzz.token_set_ratio(scrub_row.get("normalizedcompany", ""), db_row.get("normalizedcompany", ""))
        name_score = float(self.weights.company_name) * (name_sim / 100.0)
        if name_score > 1:
            score += name_score
            details.append(f"Name({name_score:.0f})")

        scrub_web = scrub_row.get("normalizedwebsite", "")
        db_web = db_row.get("normalizedwebsite", "")
        if scrub_web and db_web and scrub_web == db_web:
            website_score = float(self.weights.website)
            score += website_score
            details.append(f"Website({website_score:.0f})")
        elif scrub_web and db_web and scrub_web != db_web and website_penalty:
            score -= website_penalty
            details.append(f"WebsiteMismatch(-{website_penalty:.0f})")

        scrub_phone = scrub_row.get("normalizedphone", "")
        db_phone = db_row.get("normalizedphone", "")
        if scrub_phone and db_phone and scrub_phone == db_phone:
            phone_score = float(self.weights.phone)
            score += phone_score
            details.append(f"Phone({phone_score:.0f})")

        scrub_street = scrub_row.get("normalizedstreet", "")
        db_street = db_row.get("normalizedstreet", "")
        if scrub_street and db_street:
            street_sim = fuzz.ratio(scrub_street, db_street)
            street_score = float(self.weights.street) * (street_sim / 100.0)
            if street_score > 1:
                score += street_score
                details.append(f"Street({street_score:.0f})")

        scrub_city = scrub_row.get("city", "")
        db_city = db_row.get("city", "")
        if scrub_city and db_city:
            city_sim = fuzz.ratio(scrub_city, db_city)
            city_score = float(self.weights.city) * (city_sim / 100.0)
            if city_score > 1:
                score += city_score
                details.append(f"City({city_score:.0f})")

        if scrub_row.get("normalizedpostal") and scrub_row.get("normalizedpostal") == db_row.get("normalizedpostal"):
            postal_score = float(self.weights.postal_code)
            score += postal_score
            details.append(f"Postal({postal_score:.0f})")

        scrub_lob = scrub_row.get("normalized_lob", "")
        db_lob = db_row.get("normalized_lob", "")
        if scrub_lob and db_lob:
            lob_sim = fuzz.token_set_ratio(scrub_lob, db_lob)
            lob_score = float(self.weights.primary_lob) * (lob_sim / 100.0)
            if lob_score > 1:
                score += lob_score
                details.append(f"LOB({lob_score:.0f})")

        return score, ",".join(details)

    def _vectorizer_cache_path(self, accounts_df: pd.DataFrame) -> Path:
        search_concat = "|".join(accounts_df["search_string"].fillna("").tolist())
        digest = hashlib.sha1(search_concat.encode("utf-8")).hexdigest()
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        return self.cache_dir / f"tfidf_{digest}.pkl"

    def _get_vectorizer_and_matrix(self, accounts_df: pd.DataFrame):
        cache_path = self._vectorizer_cache_path(accounts_df)
        if cache_path.exists():
            try:
                with cache_path.open("rb") as fh:
                    vectorizer, tfidf_matrix = pickle.load(fh)
                logger.info("Loaded TF-IDF cache", extra={"path": str(cache_path)})
                return vectorizer, tfidf_matrix
            except Exception as exc:
                logger.warning("Failed to load TF-IDF cache; rebuilding", extra={"error": str(exc)})

        vectorizer = TfidfVectorizer(min_df=1, analyzer="char_wb", ngram_range=(3, 5))
        tfidf_matrix = vectorizer.fit_transform(accounts_df["search_string"])
        try:
            with cache_path.open("wb") as fh:
                pickle.dump((vectorizer, tfidf_matrix), fh)
            logger.info("Saved TF-IDF cache", extra={"path": str(cache_path)})
        except Exception as exc:
            logger.warning("Failed to write TF-IDF cache", extra={"error": str(exc), "path": str(cache_path)})
        return vectorizer, tfidf_matrix

    def _set_first_available_column(self, df: pd.DataFrame, candidates: list[str], dest: str):
        for col in candidates:
            if col in df.columns:
                df[dest] = df[col]
                return
        df[dest] = ""

    def _normalize_identifier(self, series: pd.Series, digits_only: bool = True) -> pd.Series:
        s = series.fillna("").astype(str).str.strip().str.lower()
        if digits_only:
            s = s.str.replace(r"\D", "", regex=True)
            s = s.apply(lambda x: x if x and len(x) in (5, 6) else "")
        else:
            s = s.apply(lambda x: x if len(x) >= 5 else "")
        return s

    def _warn_high_nulls(self, df: pd.DataFrame, column: str, label: str, threshold: float = 0.5):
        if column in df.columns and len(df):
            empties = (df[column] == "").sum()
            ratio = empties / len(df)
            if ratio >= threshold:
                logger.warning("High empty rate", extra={"column": label, "empty_ratio": round(ratio, 2)})

    def _build_index(self, df: pd.DataFrame, column: str):
        if column not in df.columns:
            return {}
        return {k: v.index.tolist() for k, v in df.reset_index().groupby(column) if k}

    def run(self):
        start_time = time.time()
        logger.info("Account scrub started for %s", self.input_path)

        logger.info("Stage 1/4: loading data")
        scrub_df = data_io.load_and_standardize_excel(self.input_path)
        accounts_df = data_io.load_and_standardize_excel(self.paths.account_list_path)
        contacts_df = data_io.load_and_standardize_excel(self.paths.contact_list_path)

        scrub_df["original_index"] = scrub_df.index
        original_scrub_df = scrub_df.copy()

        logger.info("Stage 2/4: renaming and normalizing")
        scrub_map = {
            "company name": "company",
            "street address": "street",
            "city": "city",
            "state": "state",
            "postalcode": "postal",
            "country": "country",
            "phone": "phone",
            "website domain": "website",
            "primary lob": "lob",
            "cms certification number (ccn)": "ccn",
            "cms certification number": "ccn",
            "ccn number": "ccn",
            "ccn": "ccn",
            "definitive id": "dhc",
            "dhc": "dhc",
            "dhc id": "dhc",
        }
        accounts_map = {
            "id": "account_id",
            "name": "company",
            "billingstreet": "street",
            "billingcity": "city",
            "billingstate": "state",
            "billingpostalcode": "postal",
            "billingcountry": "country",
            "phone": "phone",
            "website": "website",
            "primary_line_of_business__c": "lob",
            "owner.name": "owner_name",
            "ownerid": "owner_id",
            "account_status__c": "account_status",
            "total_open_opps__c": "total_open_opps",
            "ccn__c": "ccn",
            "dhcsf__dhcsf_definitive_id__c": "dhc",
        }

        scrub_df = scrub_df.rename(columns=scrub_map)
        accounts_df = accounts_df.rename(columns=accounts_map)

        self._set_first_available_column(scrub_df, ["ccn", "cms certification number (ccn)", "cms certification number", "ccn number"], "ccn")
        self._set_first_available_column(accounts_df, ["ccn"], "ccn")
        self._set_first_available_column(scrub_df, ["dhc", "definitive id", "dhc id"], "dhc")
        self._set_first_available_column(accounts_df, ["dhc"], "dhc")

        data_io.validate_required_columns(scrub_df, ["company"], "Input list")
        data_io.validate_required_columns(accounts_df, ["account_id", "company"], "Account export")
        data_io.validate_required_columns(contacts_df, ["email", "accountid"], "Contact export")

        for df in [scrub_df, accounts_df]:
            normalization.normalize_company(df, "company")
            normalization.normalize_website(df, "website")
            normalization.normalize_domain(df, "normalizedwebsite")
            normalization.normalize_phone(df, "phone")
            normalization.normalize_street(df, "street")
            normalization.normalize_postal(df, "postal")
            normalization.normalize_text_field(df, "city", "city")
            normalization.normalize_state(df, "state", "state")
            normalization.normalize_country(df, "country", "country")
            normalization.normalize_text_field(df, "lob", "normalized_lob")

        scrub_df["normalizedccn"] = self._normalize_identifier(scrub_df.get("ccn", pd.Series()), digits_only=True)
        accounts_df["normalizedccn"] = self._normalize_identifier(accounts_df.get("ccn", pd.Series()), digits_only=True)
        scrub_df["normalizeddhc"] = self._normalize_identifier(scrub_df.get("dhc", pd.Series()), digits_only=False)
        accounts_df["normalizeddhc"] = self._normalize_identifier(accounts_df.get("dhc", pd.Series()), digits_only=False)

        for col, label in [
            ("normalizedwebsite", "website"),
            ("normalizedphone", "phone"),
            ("normalizedpostal", "postal"),
            ("normalizedccn", "ccn"),
            ("normalizeddhc", "dhc"),
        ]:
            self._warn_high_nulls(scrub_df, col, f"scrub_{label}")
            self._warn_high_nulls(accounts_df, col, f"accounts_{label}")

        accounts_df["search_string"] = (
            accounts_df["normalizedcompany"].fillna("").apply(self._strip_generic_facility_tokens)
            + " "
            + accounts_df["normalizedwebsite"].fillna("")
            + " "
            + accounts_df["normalizedpostal"].fillna("")
        ).str.strip()

        postal_index = self._build_index(accounts_df, "normalizedpostal")
        state_index = self._build_index(accounts_df, "state")
        domain_index = self._build_index(accounts_df, "normalizeddomain")
        phone_index = self._build_index(accounts_df, "normalizedphone")

        logger.info("Stage 3/4: matching")
        email_matches_final = pd.DataFrame()
        if "email" in scrub_df.columns and "email" in contacts_df.columns:
            scrub_df["email"] = scrub_df["email"].astype(str)
            contacts_df["email"] = contacts_df["email"].astype(str)

            email_matched_ids = pd.merge(
                scrub_df[["original_index", "email"]],
                contacts_df[["email", "accountid"]].dropna(subset=["email"]).drop_duplicates(subset=["email"]),
                on="email",
                how="inner",
            )

            if not email_matched_ids.empty:
                email_matches_details = pd.merge(
                    email_matched_ids,
                    accounts_df,
                    left_on="accountid",
                    right_on="account_id",
                    how="left",
                )
                email_matches_details["match_score"] = 100
                email_matches_details["match_type"] = "Email Match"

                email_matches_final = email_matches_details.rename(
                    columns={"account_id": "matched_accountid", "company": "matched_company_name"}
                )
                for col in ["owner_name", "owner_id", "account_status", "total_open_opps", "lob"]:
                    if col not in email_matches_final.columns:
                        email_matches_final[col] = ""

        logger.info("Email matches found: %s", len(email_matches_final))

        ids_to_skip = email_matches_final["original_index"] if not email_matches_final.empty else []
        fuzzy_search_df = scrub_df[~scrub_df["original_index"].isin(ids_to_skip)]

        vectorizer, tfidf_matrix = self._get_vectorizer_and_matrix(accounts_df)

        all_fuzzy_matches = []
        if not fuzzy_search_df.empty:
            for _, row in fuzzy_search_df.iterrows():
                row_company = self._strip_generic_facility_tokens(row.get("normalizedcompany", ""))
                row_search_string = (
                    row_company
                    + " "
                    + row.get("normalizedwebsite", "")
                    + " "
                    + row.get("normalizedpostal", "")
                ).strip()
                if not row_search_string:
                    continue

                candidate_indices = []
                if row.get("normalizedpostal"):
                    candidate_indices = postal_index.get(row.get("normalizedpostal"), [])
                if not candidate_indices and row.get("state"):
                    candidate_indices = state_index.get(row.get("state"), [])
                if not candidate_indices and row.get("normalizeddomain"):
                    candidate_indices = domain_index.get(row.get("normalizeddomain"), [])
                if not candidate_indices and row.get("normalizedphone"):
                    candidate_indices = phone_index.get(row.get("normalizedphone"), [])
                if not candidate_indices:
                    candidate_indices = list(range(len(accounts_df)))

                vector = vectorizer.transform([row_search_string])
                tfidf_subset = tfidf_matrix[candidate_indices]
                similarities = cosine_similarity(vector, tfidf_subset).flatten()
                top_indices_local = np.argsort(similarities)[-25:][::-1]
                best_match = None
                highest_score = -1

                for local_idx in top_indices_local:
                    idx = candidate_indices[local_idx]
                    candidate = accounts_df.iloc[idx]
                    score, details = self._score_candidate(row, candidate)
                    if score > highest_score:
                        highest_score = score
                        best_match = {
                            "original_index": row["original_index"],
                            "matched_accountid": candidate["account_id"],
                            "match_score": score,
                            "match_type": details,
                            "matched_company_name": candidate.get("company"),
                            "lob": candidate.get("lob"),
                            "owner_name": candidate.get("owner_name"),
                            "owner_id": candidate.get("owner_id"),
                            "account_status": candidate.get("account_status"),
                            "total_open_opps": candidate.get("total_open_opps"),
                        }

                if highest_score >= float(self.thresholds.minimum_final_score):
                    all_fuzzy_matches.append(best_match)

        fuzzy_matches_df = pd.DataFrame(all_fuzzy_matches)
        logger.info("Fuzzy matches found: %s", len(fuzzy_matches_df))

        matched_indices = set(email_matches_final.get("original_index", pd.Series()).tolist()) | set(fuzzy_matches_df.get("original_index", pd.Series()).tolist())
        unmatched_df = scrub_df[~scrub_df["original_index"].isin(matched_indices)] if not scrub_df.empty else pd.DataFrame()

        ccn_lookup = accounts_df.dropna(subset=["normalizedccn"]).drop_duplicates("normalizedccn").set_index("normalizedccn") if "normalizedccn" in accounts_df.columns else pd.DataFrame()
        dhc_lookup = accounts_df.dropna(subset=["normalizeddhc"]).drop_duplicates("normalizeddhc").set_index("normalizeddhc") if "normalizeddhc" in accounts_df.columns else pd.DataFrame()

        deterministic_matches = []
        if not unmatched_df.empty:
            for _, row in unmatched_df.iterrows():
                matched_row = None
                if row.get("normalizedccn") and not ccn_lookup.empty and row.get("normalizedccn") in ccn_lookup.index:
                    candidate = ccn_lookup.loc[row.get("normalizedccn")]
                    matched_row = candidate
                    match_type = "CCN Match"
                elif row.get("normalizeddhc") and not dhc_lookup.empty and row.get("normalizeddhc") in dhc_lookup.index:
                    candidate = dhc_lookup.loc[row.get("normalizeddhc")]
                    matched_row = candidate
                    match_type = "DHC Match"

                if matched_row is not None:
                    deterministic_matches.append({
                        "original_index": row["original_index"],
                        "matched_accountid": matched_row.get("account_id"),
                        "match_score": 99,
                        "match_type": match_type,
                        "matched_company_name": matched_row.get("company"),
                        "lob": matched_row.get("lob"),
                        "owner_name": matched_row.get("owner_name"),
                        "owner_id": matched_row.get("owner_id"),
                        "account_status": matched_row.get("account_status"),
                        "total_open_opps": matched_row.get("total_open_opps"),
                    })

        deterministic_df = pd.DataFrame(deterministic_matches)
        logger.info("Deterministic ID matches found: %s", len(deterministic_df))

        logger.info("Stage 4/4: finalizing outputs")
        final_match_columns = [
            "original_index",
            "matched_accountid",
            "match_score",
            "match_type",
            "matched_company_name",
            "lob",
            "owner_name",
            "owner_id",
            "account_status",
            "total_open_opps",
        ]

        email_cols = [col for col in final_match_columns if col in email_matches_final.columns]
        fuzzy_cols = [col for col in final_match_columns if col in fuzzy_matches_df.columns]
        deterministic_cols = [col for col in final_match_columns if col in deterministic_df.columns]

        final_matches = pd.concat(
            [
                email_matches_final[email_cols] if not email_matches_final.empty else pd.DataFrame(columns=final_match_columns),
                fuzzy_matches_df[fuzzy_cols] if not fuzzy_matches_df.empty else pd.DataFrame(columns=final_match_columns),
                deterministic_df[deterministic_cols] if not deterministic_df.empty else pd.DataFrame(columns=final_match_columns),
            ],
            ignore_index=True,
        )

        output_df = pd.merge(original_scrub_df, final_matches, on="original_index", how="left")

        final_rename_map = {
            "matched_company_name": "Matched Company Name",
            "lob": "Matched Primary LOB",
            "owner_name": "Matched Owner Name",
            "owner_id": "Matched Owner ID",
            "account_status": "Matched Account Status",
            "total_open_opps": "Matched Total Open Opps",
        }
        output_df = output_df.rename(columns=final_rename_map)

        output_df.drop(columns=["original_index"], inplace=True, errors="ignore")

        unmatched_ids = scrub_df["original_index"]
        if not final_matches.empty:
            unmatched_ids = scrub_df[~scrub_df["original_index"].isin(final_matches["original_index"])]["original_index"]
        unmatched_df = original_scrub_df[original_scrub_df["original_index"].isin(unmatched_ids)].copy()
        unmatched_df.drop(columns=["original_index"], inplace=True, errors="ignore")

        data_io.save_to_excel(output_df, self.output_path)
        if not unmatched_df.empty:
            data_io.save_to_excel(unmatched_df, self.manual_review_path)
            logger.info("Manual review required for %s rows", len(unmatched_df))

        total_time = time.time() - start_time
        logger.info("Account workflow completed in %.2f seconds", total_time)


class ContactScrubber:
    """Handles the contact scrubbing workflow."""

    def __init__(self, settings: Settings, filename: str):
        self.settings = settings
        self.paths = settings.paths
        self.threshold = float(settings.thresholds.minimum_contact_score)
        self.weights = settings.contact_weights

        self.input_path = self.paths.output_directory / f"{filename}.xlsx"
        self.output_path = self.input_path.with_name(self.input_path.stem + "_C_OUTPUT.xlsx")
        self.contact_list_path = self.paths.contact_list_path

    def _score_candidate_contact(self, scrub_row, db_row):
        score, match_details = 0, []

        if scrub_row.get("email") and scrub_row.get("email") == db_row.get("email"):
            email_score = float(self.weights.email)
            score += email_score
            match_details.append(f"Email({email_score:.0f})")

        sim = fuzz.ratio(scrub_row.get("firstname", ""), db_row.get("firstname", ""))
        first_score = float(self.weights.first_name) * (sim / 100.0)
        if first_score > 0.1:
            score += first_score
            match_details.append(f"First({first_score:.1f})")

        sim = fuzz.ratio(scrub_row.get("lastname", ""), db_row.get("lastname", ""))
        last_score = float(self.weights.last_name) * (sim / 100.0)
        if last_score > 0.1:
            score += last_score
            match_details.append(f"Last({last_score:.1f})")

        sim = fuzz.token_set_ratio(scrub_row.get("title", ""), db_row.get("title", ""))
        title_score = float(self.weights.title) * (sim / 100.0)
        if title_score > 0.1:
            score += title_score
            match_details.append(f"Title({title_score:.1f})")

        return score, ",".join(match_details)

    def run(self):
        total_start_time = time.time()
        logger.info("Contact scrub started for %s", self.input_path)

        logger.info("Stage 1: load input + contact DB")
        scrub_df = data_io.load_and_standardize_excel(self.input_path)
        scrub_df["original_index"] = scrub_df.index

        contacts_db = data_io.load_and_standardize_excel(self.contact_list_path)
        data_io.validate_required_columns(contacts_db, ["email", "accountid"], "Contact export")

        matched_account_ids = scrub_df["matched_accountid"].dropna().unique().tolist()

        if not matched_account_ids:
            logger.info("No matched Account IDs found; skipping contact matching")
            data_io.save_to_excel(scrub_df.drop(columns=["original_index"]), self.output_path)
            return

        logger.info("Target accounts: %s", len(matched_account_ids))

        logger.info("Stage 2: filter contact database")
        candidate_contacts = contacts_db[contacts_db["accountid"].isin(matched_account_ids)]
        if candidate_contacts.empty:
            logger.info("No contacts found for matched accounts")
            data_io.save_to_excel(scrub_df.drop(columns=["original_index"]), self.output_path)
            return

        contacts_by_account = {k: g.to_dict("records") for k, g in candidate_contacts.groupby("accountid")}

        logger.info("Stage 3: scoring candidates")
        all_best_matches = []
        records_to_match = scrub_df[scrub_df["matched_accountid"].notna()]

        for _, scrub_row in records_to_match.iterrows():
            account_id = scrub_row["matched_accountid"]
            candidates = contacts_by_account.get(account_id, [])
            if not candidates:
                continue

            best_candidate_details = None
            highest_score = -1

            for candidate_row in candidates:
                score, details = self._score_candidate_contact(scrub_row, candidate_row)
                if score > highest_score:
                    highest_score = score
                    best_candidate_details = {
                        "original_index": scrub_row["original_index"],
                        "Matched_ContactID": candidate_row.get("id"),
                        "Matched_FirstName": candidate_row.get("firstname"),
                        "Matched_LastName": candidate_row.get("lastname"),
                        "Matched_Title": candidate_row.get("title"),
                        "Matched_Email": candidate_row.get("email"),
                        "Matched_ContactPhone": candidate_row.get("phone"),
                        "ContactMatchScore": score,
                        "ContactMatchType": details,
                    }

            if highest_score >= self.threshold and best_candidate_details:
                all_best_matches.append(best_candidate_details)

        logger.info("Contact matches found: %s", len(all_best_matches))

        logger.info("Stage 4: finalize outputs")
        if all_best_matches:
            matches_df = pd.DataFrame(all_best_matches)
            results_df = pd.merge(scrub_df, matches_df, on="original_index", how="left")
        else:
            results_df = scrub_df

        results_df.drop(columns=["original_index"], inplace=True, errors="ignore")
        data_io.save_to_excel(results_df, self.output_path)

        total_time = time.time() - total_start_time
        logger.info("Contact workflow completed in %.2f seconds", total_time)
