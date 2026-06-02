import os

from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = "https://api.pokemontcg.io/v2"
TCGAPI_DEV_BASE_URL = "https://api.tcgapi.dev/v1"
TCGDEX_BASE_URL = "https://api.tcgdex.net/v2"

EUR_TO_BRL = 6.35
USD_TO_BRL = 5.75
MAX_CANDIDATES = 3

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
POKEMON_TCG_API_KEY = os.getenv("POKEMON_TCG_API_KEY")
TCGAPI_DEV_KEY = os.getenv("TCGAPI_DEV_KEY", "").strip()


def parse_cors_origins() -> tuple[list[str], bool]:
    """Parse CORS_ORIGINS (comma-separated). Wildcard disables credentials (browser rule)."""
    raw = os.getenv("CORS_ORIGINS", "*").strip()
    if not raw or raw == "*":
        return ["*"], False
    origins = [origin.strip() for origin in raw.split(",") if origin.strip()]
    return (origins if origins else ["*"]), bool(origins)


def is_openai_key_configured() -> bool:
    key = (OPENAI_API_KEY or "").strip()
    if not key:
        return False
    if key in {"sk-your-openai-key", "your-openai-key", "changeme"}:
        return False
    return key.startswith("sk-")


def is_tcgapi_dev_configured() -> bool:
    return len(TCGAPI_DEV_KEY) > 0
