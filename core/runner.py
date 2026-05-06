"""
Test runner: esegue un prompt su uno o più modelli in parallelo.
"""
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from core.client import ApolloClient
from core.parser import parse_json_response, validate_response

# Web search hook (predisposto per uso futuro)
# from core.web_search import search  # noqa: F401


@dataclass
class ModelResult:
    timestamp: datetime
    model: str
    prompt_index: int | None
    tone: str | None
    language: str | None
    user_prompt: str
    raw_response: str | None = None
    parsed_json: dict | None = None
    json_parse_error: str | None = None
    schema_ok: bool = False
    schema_error: str | None = None
    latency_s: float = 0.0
    usage: Any = None
    error: str | None = None
    web_search_used: bool = False  # predisposto per Fase 4

    # Shortcut properties per visualizzazione rapida
    @property
    def preferred_brand(self) -> str:
        return (self.parsed_json or {}).get("preferred_brand", "")

    @property
    def confidence(self) -> int | None:
        return (self.parsed_json or {}).get("confidence")

    @property
    def decision(self) -> str:
        return (self.parsed_json or {}).get("decision", "")

    @property
    def success(self) -> bool:
        return self.error is None and self.schema_ok


def _run_single(
    client: ApolloClient,
    model: str,
    system_prompt: str,
    user_prompt: str,
    prompt_index: int | None,
    tone: str | None,
    language: str | None,
    temperature: float,
    max_tokens: int,
) -> ModelResult:
    t0 = time.time()
    try:
        resp = client.chat(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = resp.choices[0].message.content
        parsed, parse_err = parse_json_response(content)
        schema_ok, schema_err = False, None
        if parsed is not None and isinstance(parsed, dict):
            schema_ok, schema_err = validate_response(parsed)

        return ModelResult(
            timestamp=datetime.now(),
            model=model,
            prompt_index=prompt_index,
            tone=tone,
            language=language,
            user_prompt=user_prompt,
            raw_response=content,
            parsed_json=parsed,
            json_parse_error=parse_err,
            schema_ok=schema_ok,
            schema_error=schema_err,
            latency_s=round(time.time() - t0, 3),
            usage=getattr(resp, "usage", None),
        )
    except Exception as exc:
        return ModelResult(
            timestamp=datetime.now(),
            model=model,
            prompt_index=prompt_index,
            tone=tone,
            language=language,
            user_prompt=user_prompt,
            latency_s=round(time.time() - t0, 3),
            error=str(exc),
        )


def run_parallel(
    client: ApolloClient,
    system_prompt: str,
    prompts: list[dict],
    models: list[str],
    temperature: float = 0.2,
    max_tokens: int = 2000,
    max_workers: int = 8,
) -> list[ModelResult]:
    """
    Esegue ogni prompt su ogni modello in parallelo.

    Args:
        prompts: lista di dict con chiavi 'prompt', opzionalmente 'tone', 'language'.
        models: lista di model id da testare.

    Returns:
        Lista di ModelResult ordinata per (prompt_index, model).
    """
    tasks = [
        (i, item, model)
        for i, item in enumerate(prompts)
        for model in models
    ]

    results: list[ModelResult] = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(
                _run_single,
                client,
                model,
                system_prompt,
                item["prompt"],
                i,
                item.get("tone"),
                item.get("language"),
                temperature,
                max_tokens,
            ): (i, model)
            for i, item, model in tasks
        }
        for future in as_completed(futures):
            results.append(future.result())

    results.sort(key=lambda r: (r.prompt_index or 0, r.model))
    return results
