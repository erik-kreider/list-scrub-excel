import sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.append(str(ROOT / "src"))

from datascrubber import normalization


def test_normalize_company_and_website():
    df = pd.DataFrame({"company": ["Acme, Inc - San Jose, CA"], "website": ["https://www.acme.com/"]})
    normalization.normalize_company(df, "company")
    normalization.normalize_website(df, "website")
    assert df.loc[0, "normalizedcompany"] == "acme"
    assert df.loc[0, "normalizedwebsite"] == "acme.com"


def test_normalize_phone_and_postal():
    df = pd.DataFrame({"phone": ["(555) 555-1234"], "postal": ["12345-6789"]})
    normalization.normalize_phone(df, "phone")
    normalization.normalize_postal(df, "postal")
    assert df.loc[0, "normalizedphone"] == "5555551234"
    assert df.loc[0, "normalizedpostal"] == "12345"
