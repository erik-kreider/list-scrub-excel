# Salesforce List Scrubber

Command-line tool to scrub third-party lead/contact lists against static Salesforce exports. It catches duplicates early by pairing deterministic email/domain/phone joins with a weighted fuzzy matcher for account and contact data.

## Purpose
- Identify which incoming rows already exist as Accounts or Contacts.
- Enrich new leads with existing Salesforce context (owner, status, open opps, etc.).
- Keep the workflow offline and reproducible with static Excel inputs.

## How it works (current pipeline)
1. Load & clean: read Excel, drop Salesforce report junk columns/rows, lowercase headers, and validate required columns.
2. Normalize: standardize company, website, phone, address, postal, and simple text fields into normalized columns.
3. Match:
   - Deterministic joins: direct email matches to contacts; website/phone equality checks (configurable weights).
   - Fuzzy accounts: TF-IDF over normalized account strings + weighted field scoring with configurable penalties for location mismatches.
   - Contacts: fuzzy contact scoring scoped to already-matched account IDs.
4. Output: primary `_OUTPUT.xlsx` with appended match data plus `_MANUAL_REVIEW.xlsx` for records under the confidence threshold. Contact scrub writes `_C_OUTPUT.xlsx`.
5. Logging/validation: config is validated on startup; stages emit structured log lines (counts, timings, thresholds).

## Project layout (top-level)
- config.ini – runtime configuration (paths, thresholds, weights, penalties)
- main.py – CLI entrypoint
- requirements.txt – dependencies
- lists/ – input lists and script outputs
- src/datascrubber/ – data_io.py, normalization.py, scrubbing.py, settings.py
- tests/ – synthetic fixtures and sanity tests

## Setup
```powershell
python -m venv venv
.\venv\Scripts\Activate
pip install -r requirements.txt
```
On macOS/Linux use `source venv/bin/activate`.

## Configuration (`config.ini`)
- [Paths]: `input_directory`, `output_directory`, `account_list_path`, `contact_list_path`. Paths are validated; missing files raise a clear error.
- [Fuzzy_Matching_Thresholds]: `minimum_final_score` (accounts), `minimum_contact_score` (contacts).
- [Scoring_Weights]: field weights for account scoring (company, website, phone, street, postal_code, city, primary_lob).
- [Scoring_Penalties]: optional penalties (e.g., `location_mismatch_penalty`, `conflicting_website_penalty`).
- [Scoring_Contact]: weights for contact scoring (email, first_name, last_name, title).

If you change paths or files, keep the expected columns present:
- Account export: `id`, `name`, `billingstreet`, `billingcity`, `billingstate`, `billingpostalcode`, `billingcountry`, `phone`, `website`, `primary_line_of_business__c`, `owner.name`, `ownerid`, `account_status__c`, `total_open_opps__c`.
- Contact export: `id`, `email`, `accountid` (required), plus `firstname`, `lastname`, `title`, `phone` if available.
- Input lists: flexible headers; typically `company name`, `street address`, `city`, `state`, `postalcode`, `country`, `phone`, `website domain`, `email`.

## Usage
Run from the repository root.

**Account scrub**
```powershell
python .\main.py account my_third_party_list
```
Inputs `./lists/my_third_party_list.xlsx`; outputs `./lists/my_third_party_list_OUTPUT.xlsx` and (when needed) `./lists/my_third_party_list_MANUAL_REVIEW.xlsx`.

**Contact scrub**
```powershell
python .\main.py contact my_third_party_list_OUTPUT
```
Inputs the account output; writes `./lists/my_third_party_list_OUTPUT_C_OUTPUT.xlsx`.

## Tuning for accuracy and performance
- Raise/lower `minimum_final_score` and `minimum_contact_score` to bias toward precision vs recall.
- Adjust `Scoring_Weights` to emphasize the most reliable fields in your data (e.g., down-weight phone if noisy).
- Use `Scoring_Penalties` to gently penalize conflicting state/country instead of hard knockouts.
- Keep exports deduplicated on strong keys (email for contacts, website/phone for accounts) to avoid noisy candidates.
- Watch the logs: stage durations, counts of email vs fuzzy matches, and threshold hit rates highlight bottlenecks and tuning needs.

## Testing
Synthetic fixtures and sanity tests live under `tests/`. Run:
```powershell
python -m pytest
```

## Troubleshooting
- FileNotFoundError: check `config.ini` paths and that the list file exists in `./lists`.
- Missing column errors: re-export Salesforce reports with the required columns or rename headers to match expectations.
- Slow runs on large exports: pre-filter your exports (e.g., active accounts only) and ensure phone/website fields are normalized and deduped.

## Roadmap (suggested)
- Add cached vectorizers keyed by dataset hash to skip re-fitting on repeat runs.
- Expand normalization coverage (state/country canonicalization, domain extraction) and add evaluation harness for precision/recall tracking.
- Add richer match explanations and an audit CSV for manual review flows.
