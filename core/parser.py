"""
Parsing and validation of structured JSON responses from models.
"""
from __future__ import annotations

import json
import re


REQUIRED_KEYS = [
    "answer",
    "decision",
    "preferred_brand",
    "confidence",
    "confidence_rationale",
    "sources",
]


def _fix_newlines_in_strings(s: str) -> str:
    """Converts literal newlines inside JSON strings into escaped \\n."""
    result = []
    in_string = False
    escape_next = False
    for char in s:
        if escape_next:
            result.append(char)
            escape_next = False
            continue
        if char == "\\":
            escape_next = True
            result.append(char)
            continue
        if char == '"':
            in_string = not in_string
            result.append(char)
            continue
        if in_string and char == "\n":
            result.append("\\n")
            continue
        result.append(char)
    return "".join(result)


def parse_json_response(raw: str | None) -> tuple[dict | None, str | None]:
    """
    Attempts to parse a (potentially dirty) JSON string.
    Returns (dict, None) on success, (None, error message) otherwise.
    """
    if not raw or not raw.strip():
        return None, "empty response"

    cleaned = raw.strip()

    # Strip markdown code fences that many models add (```json ... ``` or ``` ... ```)
    md = re.match(r"^```(?:json)?\s*(.*?)\s*```$", cleaned, re.DOTALL)
    if md:
        cleaned = md.group(1)

    # Direct attempt
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError:
        pass

    # Fix literal newlines inside strings
    cleaned = _fix_newlines_in_strings(cleaned)
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError:
        pass

    # Strip residual control characters
    cleaned = re.sub(r"[\x00-\x1f\x7f](?=[^\"]*(?:\"[^\"]*\"[^\"]*)*$)", "", cleaned)
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as e:
        return None, str(e)


def validate_response(obj: dict) -> tuple[bool, str | None]:
    """
    Validates that the dict matches the expected schema.
    Returns (True, None) if valid, (False, message) otherwise.
    """
    missing = [k for k in REQUIRED_KEYS if k not in obj]
    if missing:
        return False, f"Missing keys: {missing}"
    conf = obj["confidence"]
    if not isinstance(conf, (int, float)) or not (0 <= conf <= 100):
        return False, "confidence must be a number in [0..100]"
    if not isinstance(obj["sources"], list):
        return False, "sources must be a list"
    return True, None
