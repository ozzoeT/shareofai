"""
Web search tool — Phase 4 (Tavily + tool calling).

Flow:
  1. The LLM receives a `web_search` tool definition alongside the user prompt.
  2. If it decides to search, it returns a tool_call with the query.
  3. We execute the search via Tavily and return the results to the model.
  4. The model produces its final answer grounded on the web results.
  5. URLs and snippets are stored in ModelResult for display.
"""
from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from tavily import TavilyClient

from config import TAVILY_API_KEY, TAVILY_MONTHLY_LIMIT, TAVILY_USAGE_PATH

# ---------------------------------------------------------------------------
# Usage tracking
# ---------------------------------------------------------------------------

_usage_lock = threading.Lock()


def _load_usage() -> dict:
    if TAVILY_USAGE_PATH.exists():
        return json.loads(TAVILY_USAGE_PATH.read_text())
    return {"month": _current_month(), "count": 0}


def _save_usage(data: dict) -> None:
    TAVILY_USAGE_PATH.write_text(json.dumps(data))


def _current_month() -> str:
    return datetime.now().strftime("%Y-%m")


def get_usage() -> dict:
    """Returns current month usage: {'month': '2026-05', 'count': 42, 'limit': 1000}."""
    with _usage_lock:
        data = _load_usage()
        if data["month"] != _current_month():
            data = {"month": _current_month(), "count": 0}
            _save_usage(data)
    data["limit"] = TAVILY_MONTHLY_LIMIT
    data["remaining"] = max(0, TAVILY_MONTHLY_LIMIT - data["count"])
    return data


def _check_and_increment_usage() -> None:
    """Atomically checks the monthly limit and increments the counter."""
    with _usage_lock:
        data = _load_usage()
        if data["month"] != _current_month():
            data = {"month": _current_month(), "count": 0}
        if data["count"] >= TAVILY_MONTHLY_LIMIT:
            raise RuntimeError(
                f"Tavily monthly limit reached ({TAVILY_MONTHLY_LIMIT} searches). "
                "Upgrade plan or wait for next month."
            )
        data["count"] += 1
        _save_usage(data)


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    score: float = 0.0


# ---------------------------------------------------------------------------
# Tool definition (passed to the LLM)
# ---------------------------------------------------------------------------

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for up-to-date information about veterinary products, "
            "brands, or treatments. Use this to ground your answer in current sources."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to look up.",
                }
            },
            "required": ["query"],
        },
    },
}


# ---------------------------------------------------------------------------
# Search execution
# ---------------------------------------------------------------------------

def search(query: str, max_results: int = 5) -> list[SearchResult]:
    """Executes a Tavily search and returns structured results."""
    _check_and_increment_usage()

    client = TavilyClient(api_key=TAVILY_API_KEY)
    response = client.search(query=query, max_results=max_results)

    return [
        SearchResult(
            url=r.get("url", ""),
            title=r.get("title", ""),
            snippet=r.get("content", ""),
            score=r.get("score", 0.0),
        )
        for r in response.get("results", [])
    ]


def build_search_context(results: list[SearchResult]) -> str:
    """Formats search results as context to inject into the tool response."""
    lines = ["Web search results:\n"]
    for i, r in enumerate(results, 1):
        lines.append(f"[{i}] {r.title}\nURL: {r.url}\n{r.snippet}\n")
    return "\n".join(lines)
