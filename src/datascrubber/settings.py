import logging
import os
from configparser import ConfigParser
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Paths:
    input_directory: Path
    output_directory: Path
    account_list_path: Path
    contact_list_path: Path


@dataclass
class Thresholds:
    minimum_final_score: float
    minimum_contact_score: float


@dataclass
class ScoreWeights:
    company_name: float
    website: float
    phone: float
    street: float
    postal_code: float
    city: float
    primary_lob: float


@dataclass
class Penalties:
    location_mismatch_penalty: float = 0.0
    conflicting_website_penalty: float = 0.0


@dataclass
class ContactWeights:
    email: float = 0.0
    first_name: float = 0.0
    last_name: float = 0.0
    title: float = 0.0


@dataclass
class Settings:
    paths: Paths
    thresholds: Thresholds
    weights: ScoreWeights
    penalties: Penalties
    contact_weights: ContactWeights


def _require_section(config: ConfigParser, section: str, keys: list[str]):
    if not config.has_section(section):
        raise ValueError(f"Missing required section [{section}] in config.ini")
    missing = [k for k in keys if not config.has_option(section, k)]
    if missing:
        raise ValueError(f"Missing required keys in [{section}]: {', '.join(missing)}")


def _get_float(config: ConfigParser, section: str, option: str, default: Optional[float] = None) -> float:
    if not config.has_option(section, option):
        if default is None:
            raise ValueError(f"Missing required option '{option}' in [{section}]")
        return float(default)
    try:
        return float(config.get(section, option))
    except ValueError as exc:
        raise ValueError(f"Expected a numeric value for '{option}' in [{section}]") from exc


def _resolve_path(raw_path: str) -> Path:
    return Path(os.path.expanduser(raw_path)).resolve()


def load_settings(config_path: str = "config.ini") -> Settings:
    config = ConfigParser()
    if not config.read(config_path):
        raise FileNotFoundError(f"Could not read configuration file at {config_path}")

    _require_section(
        config,
        "Paths",
        ["input_directory", "output_directory", "account_list_path", "contact_list_path"],
    )
    paths = Paths(
        input_directory=_resolve_path(config.get("Paths", "input_directory")),
        output_directory=_resolve_path(config.get("Paths", "output_directory")),
        account_list_path=_resolve_path(config.get("Paths", "account_list_path")),
        contact_list_path=_resolve_path(config.get("Paths", "contact_list_path")),
    )

    for path, label in [
        (paths.input_directory, "Paths.input_directory"),
        (paths.account_list_path, "Paths.account_list_path"),
        (paths.contact_list_path, "Paths.contact_list_path"),
    ]:
        if not path.exists():
            raise FileNotFoundError(f"{label} does not exist: {path}")

    paths.output_directory.mkdir(parents=True, exist_ok=True)

    _require_section(config, "Fuzzy_Matching_Thresholds", ["minimum_final_score", "minimum_contact_score"])
    thresholds = Thresholds(
        minimum_final_score=_get_float(config, "Fuzzy_Matching_Thresholds", "minimum_final_score"),
        minimum_contact_score=_get_float(config, "Fuzzy_Matching_Thresholds", "minimum_contact_score"),
    )

    _require_section(
        config,
        "Scoring_Weights",
        ["company_name", "website", "phone", "street", "postal_code", "city", "primary_lob"],
    )
    weights = ScoreWeights(
        company_name=_get_float(config, "Scoring_Weights", "company_name"),
        website=_get_float(config, "Scoring_Weights", "website"),
        phone=_get_float(config, "Scoring_Weights", "phone"),
        street=_get_float(config, "Scoring_Weights", "street"),
        postal_code=_get_float(config, "Scoring_Weights", "postal_code"),
        city=_get_float(config, "Scoring_Weights", "city"),
        primary_lob=_get_float(config, "Scoring_Weights", "primary_lob"),
    )

    penalties = (
        Penalties(
            location_mismatch_penalty=_get_float(config, "Scoring_Penalties", "location_mismatch_penalty", default=0),
            conflicting_website_penalty=_get_float(config, "Scoring_Penalties", "conflicting_website_penalty", default=0),
        )
        if config.has_section("Scoring_Penalties")
        else Penalties()
    )

    contact_weights = (
        ContactWeights(
            email=_get_float(config, "Scoring_Contact", "email", default=0),
            first_name=_get_float(config, "Scoring_Contact", "first_name", default=0),
            last_name=_get_float(config, "Scoring_Contact", "last_name", default=0),
            title=_get_float(config, "Scoring_Contact", "title", default=0),
        )
        if config.has_section("Scoring_Contact")
        else ContactWeights()
    )

    return Settings(
        paths=paths,
        thresholds=thresholds,
        weights=weights,
        penalties=penalties,
        contact_weights=contact_weights,
    )


def configure_logging(level: int = logging.INFO) -> logging.Logger:
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    return logging.getLogger("datascrubber")
