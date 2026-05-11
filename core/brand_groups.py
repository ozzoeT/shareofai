"""
Brand grouping / normalization utilities.

A brand group maps a canonical name to a list of aliases (alternative spellings,
capitalizations, abbreviations). When results are displayed, any alias is
replaced by the canonical name so charts and tables are consistent.

Data is stored in data/brand_groups.json as:
[
  {"canonical": "NexGard", "aliases": ["Nexgard", "NEXGARD", "nexgard spectra"]},
  ...
]
"""
from __future__ import annotations

import json
from pathlib import Path

from config import BRAND_GROUPS_PATH


def load_brand_groups(path: Path = BRAND_GROUPS_PATH) -> list[dict]:
    """Returns the list of brand groups. Returns [] if file missing or malformed."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_brand_groups(groups: list[dict], path: Path = BRAND_GROUPS_PATH) -> None:
    """Persists brand groups to disk."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(groups, f, ensure_ascii=False, indent=2)


def normalize_brand(brand: str, groups: list[dict]) -> str:
    """
    Returns the canonical name for *brand* if it matches any group's canonical
    or alias (case-insensitive). Returns the original string unchanged otherwise.
    """
    if not brand or not groups:
        return brand
    brand_lower = brand.strip().lower()
    for group in groups:
        canonical = group.get("canonical", "")
        aliases = group.get("aliases", [])
        candidates = {canonical.strip().lower()} | {a.strip().lower() for a in aliases}
        if brand_lower in candidates:
            return canonical
    return brand


def normalize_brands_in_df(df, groups: list[dict]):
    """
    Applies normalize_brand() to the 'Preferred Brand' column of a DataFrame
    in-place and returns the DataFrame.
    """
    if groups and "Preferred Brand" in df.columns:
        df["Preferred Brand"] = df["Preferred Brand"].apply(
            lambda b: normalize_brand(b, groups)
        )
    return df
