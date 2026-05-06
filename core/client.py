"""
Apollo LLM client — interfaccia OpenAI-compatible verso il gateway interno.
Gestisce autenticazione OAuth2 e inizializzazione del client.
"""
from __future__ import annotations

import threading
import time
import requests
import openai

from config import (
    APOLLO_CLIENT_ID,
    APOLLO_CLIENT_SECRET,
    APOLLO_TOKEN_URL,
    APOLLO_BASE_URL,
)

_TOKEN_TTL_SECONDS = 50 * 60  # rinnova 10 minuti prima della scadenza standard di 1h


class ApolloClient:
    """
    Client OpenAI-compatible verso Apollo (LLM gateway Boehringer Ingelheim).
    Gestisce il token OAuth2 e lo rinnova se necessario.
    """

    def __init__(
        self,
        client_id: str = APOLLO_CLIENT_ID,
        client_secret: str = APOLLO_CLIENT_SECRET,
        token_url: str = APOLLO_TOKEN_URL,
        base_url: str = APOLLO_BASE_URL,
    ) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self.token_url = token_url
        self.base_url = base_url
        self._openai_client: openai.OpenAI | None = None
        self._token_fetched_at: float = 0.0
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # Auth
    # ------------------------------------------------------------------

    def _fetch_token(self) -> str:
        resp = requests.post(
            self.token_url,
            data={
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
            },
            timeout=30,
        )
        resp.raise_for_status()
        token = resp.json().get("access_token")
        if not token:
            raise RuntimeError("No access_token returned from Apollo token endpoint")
        return token

    def _is_token_expired(self) -> bool:
        return (time.time() - self._token_fetched_at) >= _TOKEN_TTL_SECONDS

    def get_client(self) -> openai.OpenAI:
        """Restituisce il client OpenAI autenticato, rinnovando il token se scaduto.
        Thread-safe: un solo refresh alla volta anche con runner parallelo.
        """
        if self._openai_client is None or self._is_token_expired():
            with self._lock:
                # Double-check dopo aver acquisito il lock
                if self._openai_client is None or self._is_token_expired():
                    token = self._fetch_token()
                    self._token_fetched_at = time.time()
                    self._openai_client = openai.OpenAI(
                        api_key=token,
                        base_url=self.base_url,
                    )
        return self._openai_client

    def list_models(self) -> list[str]:
        """Lista i modelli disponibili sul gateway."""
        client = self.get_client()
        return [m.id for m in client.models.list()]

    # ------------------------------------------------------------------
    # Chat
    # ------------------------------------------------------------------

    def chat(
        self,
        messages: list[dict],
        model: str,
        temperature: float = 0.2,
        max_tokens: int = 2000,
    ) -> openai.types.chat.ChatCompletion:
        client = self.get_client()
        return client.chat.completions.create(
            model=model,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )
