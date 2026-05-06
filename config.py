"""
Centralised configuration for Share of AI.
"""
import os
from pathlib import Path

# --- Paths ---
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
SYSTEM_PROMPT_PATH = DATA_DIR / "system_prompt.txt"
PROMPTS_PATH = DATA_DIR / "prompts.json"

# --- Apollo / LLM Gateway ---
APOLLO_CLIENT_ID = os.getenv("APOLLO_CLIENT_ID", "")
APOLLO_CLIENT_SECRET = os.getenv("APOLLO_CLIENT_SECRET", "")
APOLLO_TOKEN_URL = os.getenv(
    "APOLLO_TOKEN_URL",
    "https://api-gw.boehringer-ingelheim.com/api/oauth/token",
)
APOLLO_BASE_URL = os.getenv(
    "APOLLO_BASE_URL",
    "https://api-gw.boehringer-ingelheim.com/apollo/llm-api",
)

# --- Available models (update based on client.models.list()) ---
AVAILABLE_MODELS: list[str] = [
    "claude_3_5_haiku",
    "claude_3_5_sonnet",
    "claude_4_5_sonnet",
    "claude_4_6_sonnet",
    "claude_4_7_opus",
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-5",
    "gpt-5-mini",
]

DEFAULT_MODELS: list[str] = ["claude_3_5_haiku", "gpt-4o-mini"]

# --- LLM parameters ---
DEFAULT_TEMPERATURE: float = 0.2
DEFAULT_MAX_TOKENS: int = 2000

# --- Available tones for prompt generation ---
AVAILABLE_TONES: list[str] = ["concise", "detailed", "reassuring", "technical", "emotional"]
AVAILABLE_LANGUAGES: list[str] = ["ita", "eng", "deu", "fra", "esp"]

# --- Web search (stub, not yet implemented — Phase 4) ---
WEB_SEARCH_ENABLED: bool = False
