# Salesforce List Scrubber

## 🚀 Introduction

This project provides a powerful and flexible command-line tool to scrub third-party lead and contact lists against static Excel exports from Salesforce. Its primary purpose is to identify which records in a new list already exist as Accounts or Contacts in your Salesforce instance, preventing duplicate data entry and enriching incoming leads with existing data.

The tool is designed to be resilient to messy data, using a sophisticated two-stage matching process that combines high-confidence email matching with advanced fuzzy logic scoring.

## ✨ Key Features

-   **Dual Scrubbing Modes**: Perform scrubs for `account` or `contact` records.
-   **Static File-Based**: Operates entirely on local Excel files (`.xlsx`), requiring no live database connection.
-   **Intelligent Data Cleaning**: Automatically handles the messy formatting of raw Salesforce report exports (removes junk rows and extra columns).
-   **Advanced Normalization**: Cleans and standardizes various data fields (company names, websites, phone numbers, addresses) before matching to increase accuracy.
-   **Two-Stage Matching Logic**:
    1.  **Email First**: A high-speed, high-confidence pre-match based on contact email addresses.
    2.  **Fuzzy Logic Scoring**: For remaining records, it uses a TF-IDF similarity search to find the best potential candidates, then scores each one based on a configurable weighted system.
-   **Highly Configurable**: Easily control matching thresholds, scoring weights for each data field, and penalties for conflicting data via a simple `config.ini` file.
-   **Flexible Penalty System**: Avoids rigid "knockout" rules by applying configurable penalties for mismatches (e.g., conflicting states), making it robust against dirty data.
-   **Clear Output**: Generates a primary output file with matched data appended, and a separate file for all unmatched records requiring manual review.

## 📂 Project Structure
# Salesforce List Scrubber

A small, local command-line tool for scrubbing third-party lead/contact lists against static Salesforce exports (Excel). It helps identify existing Accounts and Contacts for incoming lists using an email-first check followed by a robust fuzzy-matching pipeline.

## Quick summary

- Inputs: Excel (.xlsx) files — a third-party list placed in `./lists`, plus your Salesforce exports `account_list.xlsx` and `contact_list.xlsx` in the repo root (or paths set in `config.ini`).
- Modes: `account` (match company-level records) and `contact` (match individual contacts within matched accounts).
- Output: An `_OUTPUT.xlsx` file with matched metadata appended and an optional `_MANUAL_REVIEW.xlsx` containing rows that didn't meet the matching threshold.

## Features

- Automatic cleanup of raw Salesforce report exports (removes the extra first column and bracketed junk rows).
- Advanced normalizations for company names, websites, phone numbers, addresses, and postal codes.
- Two-stage matching: exact email linking (high confidence) followed by TF-IDF + cosine-similarity to surface likely account candidates and a weighted fuzzy scoring system.
- Configurable scoring weights, thresholds, and penalties through `config.ini`.

## Project layout

```
.
├── config.ini                # Configuration (paths, thresholds, weights, penalties)
├── main.py                   # CLI entrypoint
├── README.md                 # This file
├── requirements.txt          # Python dependencies
├── account_list.xlsx         # (Expected) Salesforce Account export
├── contact_list.xlsx         # (Expected) Salesforce Contact export
├── lists/                    # Input lists and script outputs
└── src/
        └── datascrubber/
                ├── data_io.py         # Excel loading/saving and SF export cleanup
                ├── normalization.py   # Normalizers for company, phone, website, postal, etc.
                └── scrubbing.py      # AccountScrubber and ContactScrubber classes (core logic)
```

## Setup

1. Create and activate a Python virtual environment (recommended):

```powershell
python -m venv venv; .\venv\Scripts\Activate
```

2. Install dependencies:

```powershell
pip install -r requirements.txt
```

3. Place your Salesforce exports in the project root or update `config.ini` paths:

- `account_list.xlsx` — Salesforce Account export (billing address fields expected)
- `contact_list.xlsx` — Salesforce Contact export (must include `Email` and `Account ID` columns)
- Put the list you want to scrub into the `lists/` folder (filename without `.xlsx` will be supplied to the CLI)

## Configuration (`config.ini`)

Key sections and options:

- [Paths]
    - `input_directory` / `output_directory` — folder for input lists and outputs (default `./lists`)
    - `account_list_path` / `contact_list_path` — paths to Salesforce exports

- [Fuzzy_Matching_Thresholds]
    - `minimum_final_score` — account-level scoring threshold for a confident fuzzy match
    - `minimum_contact_score` — threshold used by contact scrubber (falls back to 60 if not set)

- [Scoring_Weights]
    - Weights used by AccountScrubber for name, website, phone, street, postal, etc.

- [Scoring_Penalties]
    - Optional penalty values (e.g. `location_mismatch_penalty`) used instead of knockouts for mismatches

- [Scoring_Contact]
    - Weights used by ContactScrubber for `email`, `first_name`, `last_name`, and `title`.

Edit `config.ini` to tune the behavior for your data quality and matching preferences.

## Usage

Run from the repository root. Provide the mode (`account` or `contact`) and the filename (without `.xlsx`) you want to process.

Account scrub example:

```powershell
python .\main.py account my_third_party_list
```

This expects `./lists/my_third_party_list.xlsx` to exist. It will produce:

- `./lists/my_third_party_list_OUTPUT.xlsx` — the original rows with matched account metadata appended
- `./lists/my_third_party_list_MANUAL_REVIEW.xlsx` — (if any) rows that couldn't be confidently matched

Contact scrub example (runs against an account scrub output):

```powershell
python .\main.py contact my_third_party_list_OUTPUT
```

This expects the account scrub output file at `./lists/my_third_party_list_OUTPUT.xlsx`. It will produce `./lists/my_third_party_list_C_OUTPUT.xlsx` with matched contact details appended.

## How the matching works (brief)

1. Account scrub:
     - Loads input list and Salesforce export files and normalizes columns/values.
     - Performs an email-first join against the contact export to capture high-confidence hits.
     - For remaining rows, builds a TF-IDF index over normalized account fields and finds top candidate accounts.
     - Scores candidates using a weighted fuzzy logic function (name similarity, exact website/phone matches, address similarity, postal code, etc.) and applies configurable penalties for conflicting location data.

2. Contact scrub:
     - Uses the matched account IDs from an account scrub output and searches the contact export for best contact-level matches within those accounts.
     - Scores using a contact-specific weight set (email, first/last name, title) and writes contact-level match columns when the score meets the configured threshold.

## Expected inputs (column names)

- The tool attempts to be flexible by normalizing column headers to lowercase. Typical column names used by the code:
    - For input lists: `company name`, `street address`, `city`, `state`, `postalcode`, `country`, `phone`, `website domain`, `email` (when available)
    - For account export: `id`, `name`, `billingstreet`, `billingcity`, `billingstate`, `billingpostalcode`, `billingcountry`, `phone`, `website`, `primary_line_of_business__c`, `owner.name`, `ownerid`, `account_status__c`, `total_open_opps__c`
    - For contact export: must contain `email` and `accountid` columns; other fields used include `id`, `firstname`, `lastname`, `title`, `phone`.

The module `src/datascrubber/data_io.py` lowercases headers and will attempt to detect and clean raw Salesforce report artifacts.

## Developer notes

- Python modules are under `src/datascrubber/`.
- `AccountScrubber.run()` and `ContactScrubber.run()` provide the main workflows.
- Normalization helpers live in `normalization.py`. They create new columns prefixed with `normalized` (e.g., `normalizedcompany`, `normalizedphone`).

### Quick tips
- If the contact scrub raises a KeyError about missing `Email` or `Account ID`, re-export your Salesforce contact report and ensure those columns are included.
- Tune `Scoring_Weights` and `Fuzzy_Matching_Thresholds` in `config.ini` until results align with your desired precision/recall tradeoff.

## Troubleshooting

- FileNotFoundError: Check that `config.ini` points to the correct account/contact export paths and that your input filename is present in `./lists`.
- Performance: The fuzzy TF-IDF search is optimized by vectorizing account search strings and scoring the top-N candidates; for very large account exports (>100k rows) you may need to increase memory or pre-filter accounts.

## Acknowledgements

Built with pandas, scikit-learn, scikit-learn's TF-IDF, and thefuzz for string scoring.
