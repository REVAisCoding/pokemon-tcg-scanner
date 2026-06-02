import httpx
from fastapi import Header, HTTPException

import config

AUTH_TIMEOUT = httpx.Timeout(10.0)


async def get_current_user_id(authorization: str | None = Header(default=None)) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token de autenticação obrigatório.")

    if not config.is_supabase_configured():
        raise HTTPException(
            status_code=503,
            detail="Autenticação não configurada no servidor.",
        )

    token = authorization.removeprefix("Bearer ").strip()

    if not token:
        raise HTTPException(status_code=401, detail="Token de autenticação obrigatório.")

    async with httpx.AsyncClient(timeout=AUTH_TIMEOUT) as client:
        response = await client.get(
            f"{config.SUPABASE_URL}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": config.SUPABASE_SERVICE_ROLE_KEY or "",
            },
        )

    if response.status_code != 200:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")

    payload = response.json()
    user_id = payload.get("id")

    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(status_code=401, detail="Token inválido ou expirado.")

    return user_id
