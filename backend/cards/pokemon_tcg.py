import logging

import httpx

import config
from cards.mappers import get_search_names, map_tcg_card
from models import ExtractedCardInfo, ScannedCardResponse
from utils.text import escape_query_value

logger = logging.getLogger(__name__)

TCG_API_TIMEOUT = httpx.Timeout(10.0, read=25.0)


def build_search_queries(extracted: ExtractedCardInfo) -> list[str]:
    queries: list[str] = []
    number = (extracted.number or "").strip()
    set_name = (extracted.set or "").strip()
    names = get_search_names(extracted)

    if not names:
        return queries

    for name in names:
        escaped_name = escape_query_value(name)

        if number and set_name:
            queries.append(
                f'name:"{escaped_name}" number:{number} set.name:"{escape_query_value(set_name)}"'
            )

        if number:
            queries.append(f'name:"{escaped_name}" number:{number}')

        if set_name:
            queries.append(f'name:"{escaped_name}" set.name:"{escape_query_value(set_name)}"')

        queries.append(f'name:"{escaped_name}"')
        queries.append(f"name:{name}*")

    return queries


async def fetch_tcg_cards(
    client: httpx.AsyncClient,
    query: str,
    page_size: int = config.MAX_CANDIDATES,
) -> list[dict]:
    try:
        response = await client.get(
            f"{config.API_BASE_URL}/cards",
            params={"q": query, "pageSize": page_size},
        )
    except httpx.TimeoutException:
        logger.warning("TCG API timeout for query: %s", query)
        return []
    except httpx.RequestError as exc:
        logger.warning("TCG API request failed for query %s: %s", query, exc)
        return []

    if response.status_code != 200:
        logger.warning("TCG API status %s for query: %s", response.status_code, query)
        return []

    payload = response.json()
    return payload.get("data") or []


async def search_pokemontcg_candidates(
    client: httpx.AsyncClient,
    extracted: ExtractedCardInfo,
) -> list[ScannedCardResponse]:
    search_extracted = extracted
    if extracted.nameEnglish:
        search_extracted = extracted.model_copy(update={"name": extracted.nameEnglish})

    seen_ids: set[str] = set()
    pool: list[ScannedCardResponse] = []

    for query in build_search_queries(search_extracted):
        cards = await fetch_tcg_cards(client, query, page_size=20)
        for card in cards:
            mapped = map_tcg_card(card)
            if mapped.id in seen_ids:
                continue
            seen_ids.add(mapped.id)
            pool.append(mapped)

    return pool
