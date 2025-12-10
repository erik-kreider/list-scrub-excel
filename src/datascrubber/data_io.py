import logging
from pathlib import Path
import pandas as pd

logger = logging.getLogger(__name__)


def load_and_standardize_excel(filepath: str | Path) -> pd.DataFrame:
    """
    Loads an Excel file, standardizes headers to lowercase/stripped, and removes
    common Salesforce export artifacts (unnamed index column + bracketed junk rows).
    """
    path = Path(filepath).expanduser().resolve()
    if not path.exists():
        raise FileNotFoundError(f"Input file not found at: {path}")

    logger.info("Loading file %s", path)
    df = pd.read_excel(path)

    # Salesforce report cleanup: drop junk first column and bracketed rows
    if len(df.columns) > 0 and str(df.columns[0]).lower().startswith("unnamed"):
        logger.info("Salesforce export detected; cleaning header/junk rows (%s)", path)
        junk_rows = df[df.columns[0]].astype(str).str.contains(r"\[.*\]", na=False)
        df = df[~junk_rows].reset_index(drop=True)
        df = df.drop(columns=df.columns[0])

    df.columns = df.columns.str.lower().str.strip()
    logger.info("Loaded %s records from %s", len(df), path)
    return df


def validate_required_columns(df: pd.DataFrame, required: list[str], label: str):
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise KeyError(f"Missing required columns for {label}: {', '.join(missing)}")


def save_to_excel(df: pd.DataFrame, filepath: str | Path):
    """Saves a DataFrame to an Excel file, ensuring parent directories exist."""
    path = Path(filepath).expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_excel(path, index=False)
    logger.info("Output saved to %s (%s rows)", path, len(df))
