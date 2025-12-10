import sys
from pathlib import Path

import pandas as pd

# Ensure src is importable when running tests from repo root
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.append(str(ROOT / "src"))

from datascrubber.settings import load_settings


def test_load_settings_validates_and_parses(tmp_path):
    input_dir = tmp_path / "lists"
    input_dir.mkdir()
    output_dir = input_dir

    account_file = tmp_path / "account_list.xlsx"
    contact_file = tmp_path / "contact_list.xlsx"

    pd.DataFrame({"id": ["001"], "name": ["Acme"], "billingpostalcode": ["12345"]}).to_excel(account_file, index=False)
    pd.DataFrame({"id": ["c1"], "email": ["a@b.com"], "accountid": ["001"]}).to_excel(contact_file, index=False)

    config = tmp_path / "config.ini"
    config.write_text(
        f"""
[Paths]
input_directory = {input_dir}
output_directory = {output_dir}
account_list_path = {account_file}
contact_list_path = {contact_file}

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

    assert settings.paths.input_directory == input_dir.resolve()
    assert settings.paths.output_directory == output_dir.resolve()
    assert settings.thresholds.minimum_final_score == 50
    assert settings.weights.company_name == 50
    assert settings.penalties.location_mismatch_penalty == 5
    assert settings.contact_weights.email == 50
