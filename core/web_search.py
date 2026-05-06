"""
Web search tool — FASE 4 (non ancora implementato).

Questo modulo è predisposto per integrare la ricerca web nelle query LLM,
simulando l'esperienza reale di utenti su piattaforme come Gemini, ChatGPT, Claude.ai.

Architettura prevista:
- Provider multipli: Tavily, Bing, Google Custom Search, Serper
- Tool calling: iniettare search come tool nelle chiamate LLM che lo supportano
- Risultati taggati: ogni ModelResult avrà web_search_used=True e i snippet usati
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
    Esegue una ricerca web e restituisce i risultati.
    [NON IMPLEMENTATO — Fase 4]
    """
    raise NotImplementedError(
        "Web search non ancora implementato. "
        "Implementare in Fase 4 con provider Tavily/Bing/Google."
    )


def build_search_context(results: list[SearchResult]) -> str:
    """
    Formatta i risultati di ricerca come contesto da iniettare nel prompt.
    [NON IMPLEMENTATO — Fase 4]
    """
    raise NotImplementedError("Web search non ancora implementato.")
