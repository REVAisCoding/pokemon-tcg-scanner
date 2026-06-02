import os

from dotenv import load_dotenv

load_dotenv()

API_BASE_URL = "https://api.pokemontcg.io/v2"
TCGAPI_DEV_BASE_URL = "https://api.tcgapi.dev/v1"
TCGDEX_BASE_URL = "https://api.tcgdex.net/v2"
RIFTCODEX_BASE_URL = "https://api.riftcodex.com"
RIFTBOUND_TCGAPI_GAME_SLUG = "riftbound-league-of-legends-trading-card-game"

EUR_TO_BRL = 6.35
USD_TO_BRL = 5.75
MAX_CANDIDATES = 3

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
POKEMON_TCG_API_KEY = os.getenv("POKEMON_TCG_API_KEY")
TCGAPI_DEV_KEY = os.getenv("TCGAPI_DEV_KEY", "").strip()

SUPABASE_URL = (os.getenv("SUPABASE_URL") or "").strip().rstrip("/")
SUPABASE_SERVICE_ROLE_KEY = (os.getenv("SUPABASE_SERVICE_ROLE_KEY") or "").strip()
SUPABASE_STORAGE_BUCKET = (os.getenv("SUPABASE_STORAGE_BUCKET") or "scan-images").strip()
REDIS_URL = (os.getenv("REDIS_URL") or "").strip()


def parse_cors_origins() -> tuple[list[str], bool]:
    """Parse CORS origins (comma-separated). Wildcard disables credentials (browser rule)."""
    raw = (
        os.getenv("CORS_ALLOWED_ORIGINS")
        or os.getenv("CORS_ORIGINS")
        or "*"
    ).strip()
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


def is_supabase_configured() -> bool:
    return bool(SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY)


def is_redis_configured() -> bool:
    return bool(REDIS_URL)
