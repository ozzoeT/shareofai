"""
Generazione e gestione dei prompt.
Supporta:
  - caricamento da file JSON
  - generazione via LLM a partire da topic + tono + lingua
  - salvataggio di nuovi prompt
"""
from __future__ import annotations

import json
from pathlib import Path

from config import PROMPTS_PATH

# Mappa tono -> istruzione per il generatore LLM
_TONE_INSTRUCTIONS = {
    "concise": "Be brief and direct. Ask for a clear recommendation and a confidence score.",
    "detailed": (
        "Ask for a detailed comparison of options, a final recommendation, "
        "a numerical confidence score, and the sources consulted."
    ),
    "reassuring": (
        "Write as a worried or inexperienced pet owner seeking reassurance. "
        "Ask for the safest option and mention any concerns."
    ),
    "technical": (
        "Use technical/scientific language. Compare active ingredients or product categories. "
        "Request a structured decision, a quantitative confidence score, and key sources."
    ),
    "emotional": (
        "Write as someone emotionally attached to their pet. "
        "Express worry and ask which product you would feel most comfortable with."
    ),
}

_LANGUAGE_NAMES = {
    "ita": "Italian",
    "eng": "English",
    "deu": "German",
    "fra": "French",
    "esp": "Spanish",
}


def load_prompts(path: Path = PROMPTS_PATH) -> list[dict]:
    """Carica i prompt dal file JSON."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_prompts(prompts: list[dict], path: Path = PROMPTS_PATH) -> None:
    """Salva la lista di prompt nel file JSON."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)


def build_generation_prompt(topic: str, tone: str, language: str) -> str:
    """
    Costruisce il prompt da inviare al LLM per generare un nuovo prompt utente.

    Args:
        topic: argomento (es. "flea and tick prevention for a large dog")
        tone: uno dei AVAILABLE_TONES
        language: codice lingua (ita, eng, ...)
    """
    tone_instruction = _TONE_INSTRUCTIONS.get(tone, _TONE_INSTRUCTIONS["concise"])
    lang_name = _LANGUAGE_NAMES.get(language, "English")
    return (
        f"Generate a single, realistic user question about the following topic: '{topic}'.\n"
        f"Tone guidelines: {tone_instruction}\n"
        f"Write the question in {lang_name}.\n"
        f"Return only the question text, no preamble or explanation."
    )


def generate_prompt_via_llm(
    client,
    topic: str,
    tone: str,
    language: str,
    model: str,
    temperature: float = 0.7,
) -> str:
    """
    Usa il client Apollo per generare un nuovo prompt utente.

    Returns:
        Testo del prompt generato.
    """
    generation_prompt = build_generation_prompt(topic, tone, language)
    resp = client.chat(
        messages=[{"role": "user", "content": generation_prompt}],
        model=model,
        temperature=temperature,
        max_tokens=300,
    )
    return resp.choices[0].message.content.strip()


def add_prompt(
    prompts: list[dict],
    prompt_text: str,
    tone: str,
    language: str,
) -> list[dict]:
    """Aggiunge un nuovo prompt alla lista (senza salvare su disco)."""
    prompts.append({"tone": tone, "language": language, "prompt": prompt_text})
    return prompts
