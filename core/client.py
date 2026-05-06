"""
Apollo LLM client — uses the internal apollo_client module (same approach as the working notebook).
"""
from __future__ import annotations

import threading
import time

from apollo_client import OpenAI, ApolloConfig  # internal Apollo module

from config import (
    APOLLO_CLIENT_ID,
    APOLLO_CLIENT_SECRET,
)

_TOKEN_TTL_SECONDS = 50 * 60  # refresh 10 minutes before the standard 1h expiry


class ApolloClient:
    """
    Wrapper around apollo_client.OpenAI with periodic token refresh.
    Thread-safe for use with ThreadPoolExecutor.
    """

    def __init__(
        self,
        client_id: str = APOLLO_CLIENT_ID,
        client_secret: str = APOLLO_CLIENT_SECRET,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._client: OpenAI | None = None
        self._initialized_at: float = 0.0
        self._lock = threading.Lock()

    def _is_expired(self) -> bool:
        return (time.time() - self._initialized_at) >= _TOKEN_TTL_SECONDS

    def get_client(self) -> OpenAI:
        """Returns (or reinitialises) the Apollo client. Thread-safe."""
        if self._client is None or self._is_expired():
            with self._lock:
                if self._client is None or self._is_expired():
                    cfg = ApolloConfig(
                        client_id=self.client_id,
                        client_secret=self.client_secret,
                    )
                    self._client = OpenAI(config=cfg)
                    self._initialized_at = time.time()
        return self._client

    def list_models(self) -> list[str]:
        return [m.id for m in self.get_client().models.list()]

    def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
        tools: list[dict] | None = None,
    ):
        kwargs = dict(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        if tools:
            kwargs["tools"] = tools
        return self.get_client().chat.completions.create(**kwargs)
