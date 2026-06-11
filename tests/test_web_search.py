import pytest

from core import web_search
from core.web_search import SearchResult, build_search_context


@pytest.fixture(autouse=True)
def _reset_cache():
    web_search.clear_cache()
    yield
    web_search.clear_cache()


@pytest.fixture
def isolated_usage(tmp_path, monkeypatch):
    """Point usage tracking at a temp file so tests don't touch real quota."""
    usage_path = tmp_path / "tavily_usage.json"
    monkeypatch.setattr(web_search, "TAVILY_USAGE_PATH", usage_path)
    return usage_path


def _fake_tavily(monkeypatch, calls: list):
    class _FakeClient:
        def __init__(self, api_key=None):
            pass

        def search(self, query, max_results=5):
            calls.append(query)
            return {"results": [
                {"url": "https://example.com", "title": "Example", "content": "snippet", "score": 0.9}
            ]}

    monkeypatch.setattr(web_search, "TavilyClient", _FakeClient)


def test_search_calls_tavily_and_caches(monkeypatch, isolated_usage):
    calls = []
    _fake_tavily(monkeypatch, calls)

    results1 = web_search.search("flea treatment for dogs")
    results2 = web_search.search("Flea Treatment For Dogs  ")  # same query, different case/spacing

    assert len(calls) == 1  # second call served from cache
    assert results1 == results2
    assert results1[0].url == "https://example.com"


def test_search_increments_usage_only_on_cache_miss(monkeypatch, isolated_usage):
    calls = []
    _fake_tavily(monkeypatch, calls)

    web_search.search("query a")
    web_search.search("query a")
    web_search.search("query b")

    usage = web_search.get_usage()
    assert usage["count"] == 2


def test_search_raises_when_quota_exceeded(monkeypatch, isolated_usage):
    calls = []
    _fake_tavily(monkeypatch, calls)
    monkeypatch.setattr(web_search, "TAVILY_MONTHLY_LIMIT", 1)

    web_search.search("query a")
    with pytest.raises(RuntimeError):
        web_search.search("query b")


def test_clear_cache(monkeypatch, isolated_usage):
    calls = []
    _fake_tavily(monkeypatch, calls)

    web_search.search("query a")
    web_search.clear_cache()
    web_search.search("query a")

    assert len(calls) == 2


def test_build_search_context():
    results = [SearchResult(url="https://a.com", title="A", snippet="snippet a")]
    context = build_search_context(results)
    assert "https://a.com" in context
    assert "snippet a" in context
