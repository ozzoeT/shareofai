"""
Web search tool — Phase 4 (not yet implemented).

This module is a stub for integrating web search into LLM queries,
simulating the real user experience on platforms like Gemini, ChatGPT, Claude.ai.

Planned architecture:
- Multiple providers: Tavily, Bing, Google Custom Search, Serper
- Tool calling: inject search as a tool in LLM calls that support it
- Tagged results: each ModelResult will carry web_search_used=True and the snippets used
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchResult:
    url: str
    title: str
    snippet: str
    source: str


def search(query: str, max_results: int = 5) -> list[SearchResult]:
    """
    Performs a web search and returns the results.
    [NOT IMPLEMENTED — Phase 4]
    """
    raise NotImplementedError(
        "Web search not yet implemented. "
        "To be added in Phase 4 with a Tavily/Bing/Google provider."
    )


def build_search_context(results: list[SearchResult]) -> str:
    """
    Formats search results as context to inject into the prompt.
    [NOT IMPLEMENTED — Phase 4]
    """
    raise NotImplementedError("Web search not yet implemented.")
