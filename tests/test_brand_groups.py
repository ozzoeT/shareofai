import json

import pandas as pd

from core.brand_groups import (
    load_brand_groups,
    save_brand_groups,
    normalize_brand,
    normalize_brands_in_df,
)

GROUPS = [
    {"canonical": "NexGard", "aliases": ["Nexgard", "NEXGARD", "nexgard spectra"]},
    {"canonical": "Bravecto", "aliases": ["bravecto plus"]},
]


def test_normalize_brand_matches_alias_case_insensitive():
    assert normalize_brand("NEXGARD", GROUPS) == "NexGard"
    assert normalize_brand("nexgard spectra", GROUPS) == "NexGard"


def test_normalize_brand_matches_canonical():
    assert normalize_brand("nexgard", GROUPS) == "NexGard"


def test_normalize_brand_unknown_unchanged():
    assert normalize_brand("Frontline", GROUPS) == "Frontline"


def test_normalize_brand_empty_or_no_groups():
    assert normalize_brand("", GROUPS) == ""
    assert normalize_brand("Frontline", []) == "Frontline"


def test_normalize_brands_in_df():
    df = pd.DataFrame({"Preferred Brand": ["NEXGARD", "bravecto plus", "Other"]})
    normalize_brands_in_df(df, GROUPS)
    assert list(df["Preferred Brand"]) == ["NexGard", "Bravecto", "Other"]


def test_load_save_roundtrip(tmp_path):
    path = tmp_path / "brand_groups.json"
    save_brand_groups(GROUPS, path=path)
    loaded = load_brand_groups(path=path)
    assert loaded == GROUPS


def test_load_missing_file_returns_empty(tmp_path):
    path = tmp_path / "does_not_exist.json"
    assert load_brand_groups(path=path) == []


def test_load_malformed_file_returns_empty(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("not json", encoding="utf-8")
    assert load_brand_groups(path=path) == []
