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
        cleaned = md.group(1).strip()

    if not cleaned:
        return None, "empty response after stripping markdown fences"

    # Direct attempt
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError:
        pass

    # Fix literal newlines inside strings
    fixed = _fix_newlines_in_strings(cleaned)
    try:
        return json.loads(fixed), None
    except json.JSONDecodeError:
        pass

    # Strip residual control characters (exclude \t \n \r — valid JSON whitespace).
    fixed = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", fixed)
    try:
        return json.loads(fixed), None
    except json.JSONDecodeError:
        pass

    # Last resort: extract the first {...} block in case the model added preamble/postamble
    brace_match = re.search(r"\{.*\}", cleaned, re.DOTALL)
    if brace_match:
        candidate = brace_match.group(0)
        candidate = _fix_newlines_in_strings(candidate)
        candidate = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", candidate)
        try:
            return json.loads(candidate), None
        except json.JSONDecodeError as e:
            return None, str(e)

    return None, "no JSON object found in response"


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
    se = obj.get("source_evaluation")
    if se is not None:
        if not isinstance(se, dict):
            return False, "source_evaluation must be an object"
        if se.get("source_strength") not in ("strong", "mixed", "weak", None):
            return False, "source_evaluation.source_strength must be strong|mixed|weak"
        if se.get("tone_alignment") not in ("aligned", "neutral", "misaligned", None):
            return False, "source_evaluation.tone_alignment must be aligned|neutral|misaligned"
        for _key in ("source_strength_reason", "tone_detected", "decisive_factor"):
            _val = se.get(_key)
            if _val is not None and not isinstance(_val, str):
                return False, f"source_evaluation.{_key} must be a string"
    return True, None
