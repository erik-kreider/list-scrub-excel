# Salesforce List Scrubber

CLI to scrub third-party account/contact lists against static Salesforce exports. It stays offline, combines deterministic joins with fuzzy scoring, and appends match context back into Excel outputs.

## What's here
- main.py - entrypoint for account/contact scrubs.
- config_TEMPLATE.ini - copy to config.ini and point paths at your files.
- account_list.xlsx, contact_list.xlsx, list_scrub_template.xlsx - sample exports/templates.
- lists/ - place your inputs here by default (contains test fixtures).
- src/datascrubber/ - core modules (data_io.py, normalization.py, scrubbing.py, settings.py).
- tools/ - helpers for splitting/merging large Excels.
- tests/ - smoke and normalization/settings tests.
- requirements.txt - Python dependencies.

## Setup
```powershell
python -m venv venv
.\\venv\\Scripts\\activate
pip install -r requirements.txt
copy config_TEMPLATE.ini config.ini  # edit paths/thresholds as needed
```
On macOS/Linux, activate with `source venv/bin/activate` and use `cp` instead of `copy`.

## Configuration (`config.ini`)
- [Paths] (required): input_directory, output_directory, account_list_path, contact_list_path. Paths are resolved to absolute locations; inputs must exist and the output directory is created if missing.
- [Fuzzy_Matching_Thresholds]: minimum_final_score for account matches; minimum_contact_score for contact matches.
- [Scoring_Weights]: weights for account fields (company, website, phone, street, postal_code, city, primary_lob).
- [Scoring_Penalties] (optional): location_mismatch_penalty, conflicting_website_penalty.
- [Scoring_Contact] (optional): weights for contact scoring (email, first_name, last_name, title).

## Input expectations
- Incoming list: must include `company name`. Common columns mapped automatically: `street address`, `city`, `state`, `postalcode`, `country`, `phone`, `website domain`, `primary lob`, `email`, plus optional IDs (`ccn`, `cms certification number`, `definitive id`/`dhc`). Original headers are preserved in outputs.
- Account export: requires `id` and `name`; recommended fields to enrich outputs: `billingstreet`, `billingcity`, `billingstate`, `billingpostalcode`, `billingcountry`, `phone`, `website`, `primary_line_of_business__c`, `owner.name`, `ownerid`, `account_status__c`, `total_open_opps__c`, plus optional IDs `ccn__c` and `dhcsf__dhcsf_definitive_id__c`.
- Contact export: requires `email` and `accountid`; improves matching with `firstname`, `lastname`, `title`, `phone`.

## How matching works
1. Load and clean: Excel files are read, Salesforce "Unnamed" index columns/bracketed junk rows are stripped, headers are lowercased/trimmed.
2. Rename and normalize: company/site/phone/street/postal/state/country/LOB are normalized; domains are extracted; CCN/DHC identifiers are cleaned; empties are logged.
3. Account matching:
   - Direct email -> contact -> account joins (score 100).
   - Fuzzy account scoring using TF-IDF (char 3-5) plus weighted field scores; candidate set is narrowed via postal -> state -> domain -> phone lookups.
   - Deterministic ID matches on CCN/DHC for anything still unmatched.
4. Outputs:
   - `<input>_OUTPUT.xlsx` with appended columns: `matched_accountid`, `match_score`, `match_type`, `Matched Company Name`, `Matched Primary LOB`, `Matched Owner Name`, `Matched Owner ID`, `Matched Account Status`, `Matched Total Open Opps`.
   - `<input>_MANUAL_REVIEW.xlsx` containing rows with no account match.
   - TF-IDF models are cached under `<output_directory>/_cache/` keyed by the account dataset.
5. Contact scrub: runs against account output; for each matched AccountID, contact candidates are scored (email/first/last/title weights). Writes `<account_output>_C_OUTPUT.xlsx` with `Matched_ContactID/Name/Title/Email/Phone`, `ContactMatchScore`, and `ContactMatchType`.

## Usage (run from repo root)
**Account scrub**
```powershell
python .\\main.py account my_list_stem
```
Reads `./lists/my_list_stem.xlsx`; writes `./lists/my_list_stem_OUTPUT.xlsx` (+ `_MANUAL_REVIEW.xlsx` if needed).

**Contact scrub**
```powershell
python .\\main.py contact my_list_stem_OUTPUT
```
Reads the account output and writes `./lists/my_list_stem_OUTPUT_C_OUTPUT.xlsx`.

## Working with large files
- Split before scrubbing: `python tools/split_excel.py lists/big_file.xlsx --chunk-size 20000`
- Full split -> scrub -> merge: `python tools/batch_scrub.py lists/big_file.xlsx --chunk-size 20000`
- Merge arbitrary chunks: `python tools/merge_excels.py chunk1 chunk2 --output lists/merged.xlsx`

## Tuning and troubleshooting
- Lower/raise minimum_final_score or minimum_contact_score to trade precision vs recall.
- Down-weight noisy fields in [Scoring_Weights]; use penalties instead of hard filters for location/website mismatches.
- Keep account/contact exports deduplicated on strong keys (email/domain/phone/IDs) for cleaner candidates.
- Errors about missing columns usually mean headers changed; rename in Excel or adjust exports. Missing file errors point to config.ini paths.

## Testing
Synthetic fixtures live in `tests/`. Run:
```powershell
python -m pytest
```
