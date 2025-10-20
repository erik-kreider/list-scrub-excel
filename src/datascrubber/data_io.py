import pandas as pd
import os

def load_and_standardize_excel(filepath: str) -> pd.DataFrame:
    """
    Loads an Excel file and standardizes all column headers to be lowercase,
    stripped of whitespace.
    
    NEW: Now handles raw Salesforce report exports by automatically removing the
    extra first column and junk data rows (e.g., rows containing '[Account]').
    """
    expanded_path = os.path.expanduser(filepath)
    if not os.path.exists(expanded_path):
        raise FileNotFoundError(f"Input file not found at: {expanded_path}")
    
    print(f"Loading file: {expanded_path}")
    df = pd.read_excel(expanded_path)

    # --- START OF SALESFORCE CLEANUP LOGIC ---
    # Check if the first column is an unnamed column, typical of SF exports.
    if df.columns[0].startswith('unnamed'):
        print("-> Salesforce export format detected. Cleaning data...")
        # Identify junk rows by the bracket pattern in the first column.
        junk_rows = df[df.columns[0]].astype(str).str.contains(r'\[.*\]', na=False)
        
        # Keep only the rows that are NOT junk.
        df = df[~junk_rows].reset_index(drop=True)
        
        # Drop the now-useless first column.
        df = df.drop(columns=df.columns[0])

    # Standardize column headers of the now-clean data
    df.columns = df.columns.str.lower().str.strip()
    
    print(f"-> Successfully loaded and cleaned {len(df):,} records.")
    return df

def save_to_excel(df: pd.DataFrame, filepath: str):
    """Saves a DataFrame to an Excel file, creating directories if needed."""
    expanded_path = os.path.expanduser(filepath)
    os.makedirs(os.path.dirname(expanded_path), exist_ok=True)
    
    df.to_excel(expanded_path, index=False)
    print(f"✅ Output saved to: {expanded_path}")