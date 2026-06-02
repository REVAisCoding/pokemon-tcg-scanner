from functools import lru_cache

from supabase import Client, create_client

import config


@lru_cache
def get_supabase_client() -> Client:
    if not config.is_supabase_configured():
        raise RuntimeError("Supabase não configurado.")

    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
