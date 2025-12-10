import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.append(str(ROOT / "src"))

from datascrubber.settings import load_settings
from datascrubber.scrubbing import AccountScrubber, ContactScrubber


def test_account_and_contact_scrub_smoke(tmp_path):
    lists_dir = tmp_path / "lists"
    lists_dir.mkdir()

    input_df = pd.DataFrame(
        {
            "company name": ["Acme LLC"],
            "street address": ["123 Main St"],
            "city": ["Austin"],
            "state": ["TX"],
            "postalcode": ["78701"],
            "country": ["US"],
            "phone": ["555-555-1234"],
            "website domain": ["acme.com"],
            "email": ["info@acme.com"],
        }
    )
    input_df.to_excel(lists_dir / "sample.xlsx", index=False)

    account_df = pd.DataFrame(
        {
            "id": ["A001"],
            "name": ["Acme Incorporated"],
            "billingstreet": ["123 Main Street"],
            "billingcity": ["Austin"],
            "billingstate": ["TX"],
            "billingpostalcode": ["78701"],
            "billingcountry": ["US"],
            "phone": ["5555551234"],
            "website": ["acme.com"],
            "primary_line_of_business__c": ["Healthcare"],
            "owner.name": ["Owner One"],
            "ownerid": ["005"],
            "account_status__c": ["Active"],
            "total_open_opps__c": [1],
        }
    )
    account_path = tmp_path / "account_list.xlsx"
    account_df.to_excel(account_path, index=False)

    contact_df = pd.DataFrame(
        {
            "id": ["c1"],
            "email": ["info@acme.com"],
            "accountid": ["A001"],
            "firstname": ["Jane"],
            "lastname": ["Doe"],
            "title": ["VP"],
            "phone": ["5555551234"],
        }
    )
    contact_path = tmp_path / "contact_list.xlsx"
    contact_df.to_excel(contact_path, index=False)

    config = tmp_path / "config.ini"
    config.write_text(
        f"""
[Paths]
input_directory = {lists_dir}
output_directory = {lists_dir}
account_list_path = {account_path}
contact_list_path = {contact_path}

[Fuzzy_Matching_Thresholds]
minimum_final_score = 50
minimum_contact_score = 40

[Scoring_Weights]
company_name = 50
website = 40
phone = 35
street = 25
postal_code = 15
city = 10
primary_lob = 10

[Scoring_Penalties]
location_mismatch_penalty = 5
conflicting_website_penalty = 2

[Scoring_Contact]
email = 50
first_name = 20
last_name = 20
title = 10
"""
    )

    settings = load_settings(config)

    AccountScrubber(settings, "sample").run()
    account_output = pd.read_excel(lists_dir / "sample_OUTPUT.xlsx")
    assert "matched_accountid" in account_output.columns
    assert account_output["matched_accountid"].iloc[0] == "A001"

    ContactScrubber(settings, "sample_OUTPUT").run()
    contact_output = pd.read_excel(lists_dir / "sample_OUTPUT_C_OUTPUT.xlsx")
    assert "Matched_ContactID" in contact_output.columns
    assert contact_output["Matched_ContactID"].iloc[0] == "c1"
