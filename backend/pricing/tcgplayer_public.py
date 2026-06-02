import logging

import httpx

logger = logging.getLogger(__name__)

TCGPLAYER_PRODUCT_DETAILS_URL = "https://mp-search-api.tcgplayer.com/v1/product/{product_id}/details"


async def fetch_tcgplayer_public_price(tcgplayer_id: str) -> dict[str, object] | None:
    normalized_id = tcgplayer_id.strip()

    if not normalized_id.isdigit():
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                TCGPLAYER_PRODUCT_DETAILS_URL.format(product_id=normalized_id),
                headers={"Accept": "application/json"},
            )
    except httpx.HTTPError:
        logger.exception("TCGPlayer public API failed for product_id=%s", normalized_id)
        return None

    if response.status_code == 404:
        return None

    if response.status_code >= 400:
        logger.warning(
            "TCGPlayer public API error for product_id=%s status=%s",
            normalized_id,
            response.status_code,
        )
        return None

    payload = response.json()
    if not isinstance(payload, dict):
        return None

    market_price = payload.get("marketPrice")
    if isinstance(market_price, (int, float)) and market_price > 0:
        return {
            "amount": float(market_price),
            "currency": "USD",
            "source": "tcgplayer",
        }

    lowest_price = payload.get("lowestPriceWithShipping")
    if isinstance(lowest_price, (int, float)) and lowest_price > 0:
        return {
            "amount": float(lowest_price),
            "currency": "USD",
            "source": "tcgplayer",
        }

    return None
