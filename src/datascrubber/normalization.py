import pandas as pd
import numpy as np
import re

JUNK_STRINGS = {"nan", "none", "null", "n/a", "na", "-", ""}


def _clean_text_series(series: pd.Series) -> pd.Series:
    s = series.fillna("").astype(str).str.lower().str.strip()
    return s.apply(lambda x: "" if x in JUNK_STRINGS else x)


def normalize_company(df: pd.DataFrame, source_col: str) -> pd.DataFrame:
    """Advanced company name normalization."""
    if source_col not in df.columns:
        df['normalizedcompany'] = ''
        return df

    s = df[source_col].astype(str).str.lower()
    s = s.str.replace(r'\s+-\s+.*$', '', regex=True)
    s = s.str.replace(r'[^\w\s]', '', regex=True)
    suffixes = ['llc', 'inc', 'corp', 'ltd', 'lp', 'co']
    pattern = r'\b(' + '|'.join(suffixes) + r')\b'
    s = s.str.replace(pattern, '', regex=True)
    s = s.str.replace(r'\s+', ' ', regex=True).str.strip()
    df['normalizedcompany'] = s.str.replace(' ', '')
    return df


def normalize_street(df: pd.DataFrame, source_col: str) -> pd.DataFrame:
    """Safely normalizes street addresses. Creates 'normalizedstreet' column."""
    if source_col not in df.columns:
        df['normalizedstreet'] = ''
        return df

    s = _clean_text_series(df[source_col])
    s = s.str.split(r'\s(?:#|apt|suite|ste)\s?\w*', n=1, expand=True)[0]
    s = s.str.replace(r'[^\w\s]', '', regex=True)
    s = s.str.replace(r'\s+', '', regex=True).str.strip()
    df['normalizedstreet'] = s
    return df


def normalize_postal(df: pd.DataFrame, source_col: str) -> pd.DataFrame:
    """Safely normalizes postal codes to 5 digits. Creates 'normalizedpostal'."""
    if source_col not in df.columns:
        df['normalizedpostal'] = ''
        return df

    def format_postal(code):
        if pd.isna(code):
            return ''
        digits = ''.join(filter(str.isdigit, str(code)))
        return digits[:5].zfill(5) if len(digits) >= 5 else ''

    df['normalizedpostal'] = df[source_col].apply(format_postal)
    return df


def normalize_website(df: pd.DataFrame, source_col: str) -> pd.DataFrame:
    """Safely normalizes website URLs. Creates 'normalizedwebsite' column."""
    if source_col not in df.columns:
        df['normalizedwebsite'] = ''
        return df

    s = _clean_text_series(df[source_col])
    s = s.str.replace(r'^(https?://)?(www\.)?', '', regex=True)
    s = s.str.split('/').str[0]
    s = s.str.split('?').str[0]
    df['normalizedwebsite'] = s.str.strip()
    return df


def normalize_phone(df: pd.DataFrame, source_col: str) -> pd.DataFrame:
    """Normalizes phone numbers to a consistent digit-only format."""
    if source_col not in df.columns:
        df['normalizedphone'] = ''
        return df

    df['normalizedphone'] = df[source_col].astype(str).str.extractall(r'([0-9])').unstack().fillna('').agg(''.join, axis=1)
    return df


def normalize_text_field(df: pd.DataFrame, source_col: str, dest_col: str) -> pd.DataFrame:
    if source_col not in df.columns:
        df[dest_col] = ''
        return df
    df[dest_col] = _clean_text_series(df[source_col])
    return df


def normalize_state(df: pd.DataFrame, source_col: str, dest_col: str = "state") -> pd.DataFrame:
    """Canonicalize US state names/abbreviations to two-letter lowercase codes."""
    if source_col not in df.columns:
        df[dest_col] = ''
        return df

    state_map = {
        "alabama": "al", "alaska": "ak", "arizona": "az", "arkansas": "ar",
        "california": "ca", "colorado": "co", "connecticut": "ct", "delaware": "de",
        "florida": "fl", "georgia": "ga", "hawaii": "hi", "idaho": "id",
        "illinois": "il", "indiana": "in", "iowa": "ia", "kansas": "ks",
        "kentucky": "ky", "louisiana": "la", "maine": "me", "maryland": "md",
        "massachusetts": "ma", "michigan": "mi", "minnesota": "mn", "mississippi": "ms",
        "missouri": "mo", "montana": "mt", "nebraska": "ne", "nevada": "nv",
        "new hampshire": "nh", "new jersey": "nj", "new mexico": "nm", "new york": "ny",
        "north carolina": "nc", "north dakota": "nd", "ohio": "oh", "oklahoma": "ok",
        "oregon": "or", "pennsylvania": "pa", "rhode island": "ri", "south carolina": "sc",
        "south dakota": "sd", "tennessee": "tn", "texas": "tx", "utah": "ut",
        "vermont": "vt", "virginia": "va", "washington": "wa", "west virginia": "wv",
        "wisconsin": "wi", "wyoming": "wy", "district of columbia": "dc",
    }

    def canon(val: str) -> str:
        if pd.isna(val):
            return ""
        v = str(val).strip().lower()
        if not v:
            return ""
        if v in state_map.values():
            return v
        return state_map.get(v, v)

    df[dest_col] = df[source_col].apply(canon)
    return df


def normalize_country(df: pd.DataFrame, source_col: str, dest_col: str = "country") -> pd.DataFrame:
    """Canonicalize common country names to two-letter lowercase ISO-ish codes."""
    if source_col not in df.columns:
        df[dest_col] = ''
        return df

    country_map = {
        "united states": "us",
        "united states of america": "us",
        "usa": "us",
        "us": "us",
        "canada": "ca",
        "ca": "ca",
        "united kingdom": "gb",
        "uk": "gb",
        "great britain": "gb",
        "australia": "au",
        "au": "au",
    }

    def canon(val: str) -> str:
        if pd.isna(val):
            return ""
        v = str(val).strip().lower()
        if not v:
            return ""
        return country_map.get(v, v)

    df[dest_col] = df[source_col].apply(canon)
    return df


def normalize_domain(df: pd.DataFrame, source_col: str, dest_col: str = "normalizeddomain") -> pd.DataFrame:
    """Extract a base domain (strip scheme, path, query, leading subdomains)."""
    if source_col not in df.columns:
        df[dest_col] = ''
        return df

    def extract(host: str) -> str:
        if pd.isna(host):
            return ""
        h = str(host).lower().strip()
        h = re.sub(r"^(https?://)", "", h)
        h = re.sub(r"^www\.", "", h)
        h = h.split("/")[0].split("?")[0]
        if not h:
            return ""
        parts = h.split(".")
        if len(parts) <= 2:
            return h
        sld = ".".join(parts[-2:])
        sld_exceptions = {"co.uk", "org.uk", "ac.uk", "com.au", "net.au", "co.jp"}
        if sld in sld_exceptions and len(parts) >= 3:
            return ".".join(parts[-3:])
        return sld

    df[dest_col] = df[source_col].apply(extract)
    return df
