"""
Prompt management and generation.
Supports:
  - loading from JSON file
  - LLM-based generation from topic + tone + language
  - saving new prompts to the library
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
    """Loads prompts from the JSON file. Returns [] if file is missing or malformed."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_prompts(prompts: list[dict], path: Path = PROMPTS_PATH) -> None:
    """Saves the prompt list to the JSON file."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)


def build_generation_prompt(topic: str, tone: str, language: str) -> str:
    """
    Builds the meta-prompt to send to the LLM for generating a new user prompt.

    Args:
        topic: subject matter (e.g. "flea and tick prevention for a large dog")
        tone: one of AVAILABLE_TONES
        language: language code (ita, eng, ...)
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
    Uses the Apollo client to generate a new user prompt.

    Returns:
        Generated prompt text.
    """
    generation_prompt = build_generation_prompt(topic, tone, language)
    resp = client.chat(
        messages=[{"role": "user", "content": generation_prompt}],
        model=model,
        temperature=temperature,
        max_tokens=300,
    )
    content = resp.choices[0].message.content
    if not content:
        raise ValueError("LLM returned empty content for prompt generation.")
    return content.strip()


def _build_multi_generation_prompt(topic: str, combinations: list[tuple[str, str]]) -> str:
    """
    Builds a meta-prompt asking the LLM to generate multiple prompts in one shot.
    Each combination is a (tone, language) pair.
    """
    items = "\n".join(
        f"  {i+1}. tone={tone}, language={_LANGUAGE_NAMES.get(lang, lang)}, "
        f"tone_guidelines={_TONE_INSTRUCTIONS.get(tone, _TONE_INSTRUCTIONS['concise'])}"
        for i, (tone, lang) in enumerate(combinations)
    )
    return (
        f"Generate {len(combinations)} realistic veterinary product purchase questions "
        f"about the following topic: '{topic}'.\n\n"
        f"For each item below produce one question following the specified tone and language:\n"
        f"{items}\n\n"
        f"Return ONLY a valid JSON array with exactly {len(combinations)} objects, "
        f"each with keys \"tone\" (the tone code, e.g. concise), "
        f"\"language\" (the language code, e.g. ita), and \"prompt\" (the question text). "
        f"No markdown fences, no explanation — raw JSON only."
    )


def generate_prompts_batch_via_llm(
    client,
    topic: str,
    combinations: list[tuple[str, str]],
    model: str,
    temperature: float = 0.7,
    batch_size: int = 10,
) -> list[dict]:
    """
    Generates multiple prompts with a small number of LLM calls.
    Splits *combinations* into chunks of *batch_size* and calls the LLM once per chunk.

    Args:
        combinations: list of (tone, language) pairs to generate.
        batch_size: max prompts requested in a single call (default 10).

    Returns:
        List of dicts with keys 'tone', 'language', 'prompt'.
    """
    import math

    results: list[dict] = []
    n_chunks = math.ceil(len(combinations) / batch_size)

    for chunk_idx in range(n_chunks):
        chunk = combinations[chunk_idx * batch_size : (chunk_idx + 1) * batch_size]
        meta_prompt = _build_multi_generation_prompt(topic, chunk)
        resp = client.chat(
            messages=[{"role": "user", "content": meta_prompt}],
            model=model,
            temperature=temperature,
            max_tokens=300 * len(chunk),
        )
        content = (resp.choices[0].message.content or "").strip()

        # Strip optional markdown fences
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
            content = content.strip()

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"LLM returned invalid JSON in chunk {chunk_idx+1}: {exc}\n{content}") from exc

        if not isinstance(parsed, list):
            raise ValueError(f"Expected a JSON array, got {type(parsed).__name__}")

        # Merge parsed items with original (tone, lang) to ensure correctness
        for i, item in enumerate(parsed):
            tone, lang = chunk[i] if i < len(chunk) else (item.get("tone", ""), item.get("language", ""))
            results.append({
                "tone": item.get("tone", tone),
                "language": item.get("language", lang),
                "prompt": item.get("prompt", ""),
            })

    return results


def add_prompt(
    prompts: list[dict],
    prompt_text: str,
    tone: str,
    language: str,
    category: str | None = None,
) -> list[dict]:
    """Adds a new prompt to the list (without saving to disk)."""
    entry: dict = {"tone": tone, "language": language, "prompt": prompt_text}
    if category:
        entry["category"] = category
    prompts.append(entry)
    return prompts
