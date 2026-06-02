import logging

import httpx
from fastapi import HTTPException

import config

logger = logging.getLogger(__name__)


def extract_tcgapi_dev_price(prices: list[dict[str, object]]) -> dict[str, object] | None:
    for entry in prices:
        market_price = entry.get("market_price")
        if isinstance(market_price, (int, float)) and market_price > 0:
            return {
                "amount": float(market_price),
                "currency": "USD",
                "source": "tcgplayer",
                "updatedAt": entry.get("last_updated_at"),
            }

    for entry in prices:
        median_price = entry.get("median_price")
        if isinstance(median_price, (int, float)) and median_price > 0:
            return {
                "amount": float(median_price),
                "currency": "USD",
                "source": "tcgplayer",
                "updatedAt": entry.get("last_updated_at"),
            }

    for entry in prices:
        low_price = entry.get("low_price")
        if isinstance(low_price, (int, float)) and low_price > 0:
            return {
                "amount": float(low_price),
                "currency": "USD",
                "source": "tcgplayer",
                "updatedAt": entry.get("last_updated_at"),
            }

    return None


async def fetch_riftbound_price(tcgplayer_id: str) -> dict[str, object] | None:
    normalized_id = tcgplayer_id.strip()

    if not normalized_id.isdigit():
        raise HTTPException(status_code=400, detail="ID do TCGPlayer inválido.")

    if not config.is_tcgapi_dev_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "TCGAPI_DEV_KEY não configurada. Crie uma chave gratuita em "
                "https://tcgapi.dev e adicione ao backend/.env"
            ),
        )

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{config.TCGAPI_DEV_BASE_URL}/cards/tcgplayer/{normalized_id}",
                headers={"X-API-Key": config.TCGAPI_DEV_KEY},
            )
    except httpx.HTTPError as exc:
        logger.exception("TCG API request failed for tcgplayer_id=%s", normalized_id)
        raise HTTPException(
            status_code=502,
            detail="Não foi possível consultar o preço da carta.",
        ) from exc

    if response.status_code == 404:
        return None

    if response.status_code >= 400:
        logger.warning(
            "TCG API error for tcgplayer_id=%s status=%s body=%s",
            normalized_id,
            response.status_code,
            response.text[:300],
        )
        raise HTTPException(status_code=502, detail="Não foi possível consultar o preço da carta.")

    payload = response.json()
    data = payload.get("data") if isinstance(payload, dict) else None
    prices = data.get("prices") if isinstance(data, dict) else None
    normalized_prices = prices if isinstance(prices, list) else []
    return extract_tcgapi_dev_price(normalized_prices)
