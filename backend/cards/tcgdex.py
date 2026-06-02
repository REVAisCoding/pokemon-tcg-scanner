import logging

import httpx

import config
from cards.mappers import (
    get_search_names,
    local_id_variants,
    map_tcgdex_card,
)
from models import ExtractedCardInfo, ScannedCardResponse

logger = logging.getLogger(__name__)

TCGDEX_TIMEOUT = httpx.Timeout(4.0, connect=4.0, read=6.0)
_tcgdex_available: bool | None = None


async def check_tcgdex_available(client: httpx.AsyncClient) -> bool:
    global _tcgdex_available

    if _tcgdex_available is not None:
        return _tcgdex_available

    try:
        response = await client.get(
            f"{config.TCGDEX_BASE_URL}/en/sets",
            timeout=TCGDEX_TIMEOUT,
        )
        _tcgdex_available = response.status_code == 200
    except httpx.RequestError:
        _tcgdex_available = False

    if not _tcgdex_available:
        logger.warning("TCGdex unavailable — using Pokémon TCG API only for candidates")

    return _tcgdex_available


async def fetch_tcgdex_card_list(
    client: httpx.AsyncClient,
    lang: str,
    params: dict[str, str],
) -> list[dict]:
    try:
        response = await client.get(
            f"{config.TCGDEX_BASE_URL}/{lang}/cards",
            params=params,
            timeout=TCGDEX_TIMEOUT,
        )
    except httpx.TimeoutException:
        logger.warning("TCGdex timeout for params: %s", params)
        return []
    except httpx.RequestError as exc:
        logger.warning("TCGdex request failed for params %s: %s", params, exc)
        return []

    if response.status_code != 200:
        logger.warning("TCGdex status %s for params: %s", response.status_code, params)
        return []

    payload = response.json()
    return payload if isinstance(payload, list) else []


async def fetch_tcgdex_card_detail(
    client: httpx.AsyncClient,
    lang: str,
    card_id: str,
) -> dict | None:
    try:
        response = await client.get(
            f"{config.TCGDEX_BASE_URL}/{lang}/cards/{card_id}",
            timeout=TCGDEX_TIMEOUT,
        )
    except httpx.RequestError as exc:
        logger.warning("TCGdex detail failed for %s: %s", card_id, exc)
        return None

    if response.status_code != 200:
        return None

    payload = response.json()
    return payload if isinstance(payload, dict) else None


async def search_tcgdex_candidates(
    client: httpx.AsyncClient,
    extracted: ExtractedCardInfo,
    lang: str,
) -> list[ScannedCardResponse]:
    names = get_search_names(extracted)
    if not names:
        return []

    number_briefs: list[dict] = []
    name_briefs: list[dict] = []
    seen_brief_ids: set[str] = set()
    number_variants = local_id_variants(extracted.number)

    for name in names:
        if number_variants:
            for local_id in number_variants:
                matches = await fetch_tcgdex_card_list(
                    client,
                    lang,
                    {"name": name, "localId": local_id},
                )
                for match in matches:
                    if match["id"] not in seen_brief_ids:
                        seen_brief_ids.add(match["id"])
                        number_briefs.append(match)

        matches = await fetch_tcgdex_card_list(client, lang, {"name": name})
        for match in matches:
            if match["id"] not in seen_brief_ids:
                seen_brief_ids.add(match["id"])
                name_briefs.append(match)

    brief_cards = number_briefs if number_briefs else name_briefs

    candidates: list[ScannedCardResponse] = []
    for brief in brief_cards:
        detail = await fetch_tcgdex_card_detail(client, lang, brief["id"])
        if not detail:
            continue
        candidates.append(map_tcgdex_card(detail))

    return candidates
