import logging

import httpx

import config

logger = logging.getLogger(__name__)


async def fetch_tcgplayer_id_by_riftbound_id(riftbound_id: str) -> str | None:
    normalized_id = riftbound_id.strip().lower()

    if not normalized_id:
        return None

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{config.RIFTCODEX_BASE_URL}/cards/riftbound/{normalized_id}",
            )
    except httpx.HTTPError:
        logger.exception("Riftcodex request failed for riftbound_id=%s", normalized_id)
        return None

    if response.status_code == 404:
        return None

    if response.status_code >= 400:
        logger.warning(
            "Riftcodex error for riftbound_id=%s status=%s",
            normalized_id,
            response.status_code,
        )
        return None

    payload = response.json()
    cards = payload if isinstance(payload, list) else [payload] if isinstance(payload, dict) else []

    for card in cards:
        if not isinstance(card, dict):
            continue

        tcgplayer_id = card.get("tcgplayer_id")
        if isinstance(tcgplayer_id, str) and tcgplayer_id.strip().isdigit():
            return tcgplayer_id.strip()

    return None
