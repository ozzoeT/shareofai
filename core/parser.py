"""
Parsing e validazione delle risposte JSON strutturate dei modelli.
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
    """Converte newline letterali dentro stringhe JSON in \\n escaped."""
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


def parse_json_response(raw: str) -> tuple[dict | None, str | None]:
    """
    Tenta di parsare una stringa JSON (potenzialmente sporca).
    Restituisce (dict, None) in caso di successo, (None, errore) altrimenti.
    """
    cleaned = raw.strip()

    # Prova diretta
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError:
        pass

    # Fix newline letterali nelle stringhe
    cleaned = _fix_newlines_in_strings(cleaned)
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError:
        pass

    # Rimuovi caratteri di controllo residui
    cleaned = re.sub(r"[\x00-\x1f\x7f](?=[^\"]*(?:\"[^\"]*\"[^\"]*)*$)", "", cleaned)
    try:
        return json.loads(cleaned), None
    except json.JSONDecodeError as e:
        return None, str(e)


def validate_response(obj: dict) -> tuple[bool, str | None]:
    """
    Valida che il dict rispetti lo schema atteso.
    Restituisce (True, None) se valido, (False, messaggio) altrimenti.
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
