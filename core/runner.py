"""
Test runner: executes a prompt against one or more models in parallel.
Supports both standard mode and web search mode (tool calling).
"""
from __future__ import annotations

import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generator

from core.client import ApolloClient
from core.parser import parse_json_response, validate_response


@dataclass
class ModelResult:
    timestamp: datetime
    model: str
    prompt_index: int | None
    tone: str | None
    language: str | None
    user_prompt: str
    category: str | None = None
    raw_response: str | None = None
    parsed_json: dict | None = None
    json_parse_error: str | None = None
    schema_ok: bool = False
    schema_error: str | None = None
    latency_s: float = 0.0
    usage: Any = None
    error: str | None = None
    web_search_used: bool = False
    search_results: list[dict] = field(default_factory=list)  # [{url, title, snippet}]

    # Shortcut properties for quick display
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
    def source_evaluation(self) -> dict:
        return (self.parsed_json or {}).get("source_evaluation") or {}

    @property
    def success(self) -> bool:
        return self.error is None and self.schema_ok


# ---------------------------------------------------------------------------
# Single run — standard (no web search)
# ---------------------------------------------------------------------------

def _run_single(
    client: ApolloClient,
    model: str,
    system_prompt: str,
    user_prompt: str,
    prompt_index: int | None,
    tone: str | None,
    language: str | None,
    category: str | None,
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
        choice = resp.choices[0]
        content = choice.message.content
        if not content:
            raise ValueError(f"Empty response (finish_reason={choice.finish_reason!r})")
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
            category=category,
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
            category=category,
            user_prompt=user_prompt,
            latency_s=round(time.time() - t0, 3),
            error=str(exc),
        )


# ---------------------------------------------------------------------------
# Single run — with web search (tool calling loop)
# ---------------------------------------------------------------------------

def _run_single_with_search(
    client: ApolloClient,
    model: str,
    system_prompt: str,
    user_prompt: str,
    prompt_index: int | None,
    tone: str | None,
    language: str | None,
    category: str | None,
    temperature: float,
    max_tokens: int,
) -> ModelResult:
    from core.web_search import WEB_SEARCH_TOOL, search, build_search_context

    t0 = time.time()
    search_results: list[dict] = []

    try:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        # --- First call: offer the search tool ---
        resp = client.chat(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            tools=[WEB_SEARCH_TOOL],
        )

        choice = resp.choices[0]

        # --- Tool calling loop ---
        _MAX_TOOL_ITERATIONS = 2
        _tool_iter = 0
        while choice.finish_reason == "tool_calls":
            _tool_iter += 1
            if _tool_iter > _MAX_TOOL_ITERATIONS:
                raise RuntimeError(
                    f"Tool-call loop exceeded {_MAX_TOOL_ITERATIONS} iterations — aborting."
                )
            # Serialize assistant message to plain dict
            # (Pydantic objects from the SDK are not accepted as message dicts by the gateway)
            # content is None when the model returns only tool_calls — use "" for gateway compat
            messages.append({
                "role": "assistant",
                "content": choice.message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in choice.message.tool_calls
                ],
            })

            # GPT can return multiple parallel tool calls — each needs its own tool message.
            for tool_call in choice.message.tool_calls:
                query = json.loads(tool_call.function.arguments).get("query", user_prompt)
                results = search(query)
                search_results.extend([
                    {"url": r.url, "title": r.title, "snippet": r.snippet}
                    for r in results
                ])
                context = build_search_context(results)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": context,
                })

            resp = client.chat(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens,
                tools=[WEB_SEARCH_TOOL],
            )
            choice = resp.choices[0]

        # --- Final answer ---
        content = choice.message.content
        finish_reason = choice.finish_reason
        if not content:
            raise ValueError(f"Empty response (finish_reason={finish_reason!r})")
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
            category=category,
            user_prompt=user_prompt,
            raw_response=content,
            parsed_json=parsed,
            json_parse_error=parse_err,
            schema_ok=schema_ok,
            schema_error=schema_err,
            latency_s=round(time.time() - t0, 3),
            usage=getattr(resp, "usage", None),
            web_search_used=bool(search_results),
            search_results=search_results,
        )

    except Exception as exc:
        return ModelResult(
            timestamp=datetime.now(),
            model=model,
            prompt_index=prompt_index,
            tone=tone,
            language=language,
            category=category,
            user_prompt=user_prompt,
            latency_s=round(time.time() - t0, 3),
            error=str(exc),
            web_search_used=bool(search_results),
            search_results=search_results,
        )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _build_futures(
    executor: ThreadPoolExecutor,
    runner,
    client: ApolloClient,
    system_prompt: str,
    prompts: list[dict],
    models: list[str],
    temperature: float,
    max_tokens: int,
) -> dict:
    tasks = [
        (i, item, model)
        for i, item in enumerate(prompts)
        for model in models
    ]
    return {
        executor.submit(
            runner,
            client,
            model,
            system_prompt,
            item["prompt"],
            i,
            item.get("tone"),
            item.get("language"),
            item.get("category"),
            temperature,
            max_tokens,
        ): (i, model)
        for i, item, model in tasks
    }


def run_streaming(
    client: ApolloClient,
    system_prompt: str,
    prompts: list[dict],
    models: list[str],
    temperature: float = 0.2,
    max_tokens: int = 2000,
    max_workers: int = 8,
    use_web_search: bool = False,
) -> Generator[ModelResult, None, None]:
    """
    Same as run_parallel but yields each ModelResult as soon as it completes,
    allowing the caller to update progress and autosave incrementally.
    """
    runner = _run_single_with_search if use_web_search else _run_single
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = _build_futures(
            executor, runner, client, system_prompt, prompts, models, temperature, max_tokens
        )
        for future in as_completed(futures):
            yield future.result()


def run_parallel(
    client: ApolloClient,
    system_prompt: str,
    prompts: list[dict],
    models: list[str],
    temperature: float = 0.2,
    max_tokens: int = 2000,
    max_workers: int = 8,
    use_web_search: bool = False,
) -> list[ModelResult]:
    """
    Runs every prompt against every model in parallel.

    Returns:
        List of ModelResult sorted by (prompt_index, model).
    """
    results = list(run_streaming(
        client, system_prompt, prompts, models, temperature, max_tokens, max_workers, use_web_search
    ))

    results.sort(key=lambda r: (r.prompt_index or 0, r.model))
    return results
