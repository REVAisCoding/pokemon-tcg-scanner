import logging
import re

import httpx

import config
from models import ExtractedCardInfo, ScannedCardResponse

logger = logging.getLogger(__name__)

SCRYFALL_API_BASE_URL = "https://api.scryfall.com"
SCRYFALL_USER_AGENT = "PokemonApp/1.0 (card-scan-backend)"
MAGIC_ACCENT_COLOR = "#C79B3B"
RIFTBOUND_ACCENT_COLOR = "#C89B3C"
RIFTCODEX_SEARCH_PAGE_SIZE = 80
RIFTCODEX_MAX_SEARCH_PAGES = 3

TCG_API_TIMEOUT = httpx.Timeout(10.0, read=25.0)


def _normalize_collector_number(value: str | None) -> str | None:
    if not value:
        return None

    match = re.search(r"\d+", value)
    if not match:
        return None

    normalized = match.group(0).lstrip("0") or "0"
    return normalized


def _normalize_set_code(value: str | None) -> str | None:
    if not value:
        return None

    return value.strip().lower()


def _build_scryfall_query(name: str, extracted: ExtractedCardInfo) -> str:
    trimmed_name = name.strip()
    set_code = _normalize_set_code(extracted.set)
    collector_number = _normalize_collector_number(extracted.number)

    if set_code and collector_number:
        return f'!"{trimmed_name}" set:{set_code} cn:{collector_number}'

    if set_code:
        return f'!"{trimmed_name}" set:{set_code}'

    return trimmed_name


def _resolve_scryfall_image(card: dict) -> str:
    image_uris = card.get("image_uris") or {}
    for key in ("normal", "large", "small"):
        if image_uris.get(key):
            return image_uris[key]

    faces = card.get("card_faces") or []
    if faces:
        face_uris = faces[0].get("image_uris") or {}
        for key in ("normal", "large", "small"):
            if face_uris.get(key):
                return face_uris[key]

    return f"{SCRYFALL_API_BASE_URL}/cards/{card['id']}?format=image&version=normal"


def _map_magic_card(card: dict) -> ScannedCardResponse:
    collector_number = card.get("collector_number") or ""
    formatted_number = (
        collector_number if collector_number.startswith("#") else f"#{collector_number}"
    )
    card_type = card.get("type_line") or (card.get("card_faces") or [{}])[0].get(
        "type_line", ""
    )
    rarity = card.get("rarity") or None
    formatted_rarity = rarity.capitalize() if isinstance(rarity, str) and rarity else None

    return ScannedCardResponse(
        id=f"magic-{card['id']}",
        name=card.get("name") or "",
        setName=card.get("set_name") or "",
        number=formatted_number,
        type=card_type,
        imageUrl=_resolve_scryfall_image(card),
        accentColor=MAGIC_ACCENT_COLOR,
        rarity=formatted_rarity,
    )


def _score_magic_candidate(card: dict, extracted: ExtractedCardInfo) -> int:
    score = 0
    set_code = _normalize_set_code(extracted.set)
    collector_number = _normalize_collector_number(extracted.number)

    if set_code and str(card.get("set", "")).lower() == set_code:
        score += 10

    if collector_number and _normalize_collector_number(card.get("collector_number")) == collector_number:
        score += 5

    return score


async def _fetch_scryfall_cards(client: httpx.AsyncClient, query: str) -> list[dict]:
    params = {"q": query, "unique": "cards", "order": "name"}
    response = await client.get(
        f"{SCRYFALL_API_BASE_URL}/cards/search",
        params=params,
        headers={
            "Accept": "application/json",
            "User-Agent": SCRYFALL_USER_AGENT,
        },
    )

    if response.status_code == 404:
        return []

    response.raise_for_status()
    payload = response.json()
    data = payload.get("data")

    if not isinstance(data, list):
        return []

    return data


async def search_magic_candidates(
    extracted: ExtractedCardInfo,
    detected_name: str,
) -> list[ScannedCardResponse]:
    query_name = detected_name.strip()

    if not query_name:
        return []

    scryfall_query = _build_scryfall_query(query_name, extracted)

    async with httpx.AsyncClient(timeout=TCG_API_TIMEOUT) as client:
        cards = await _fetch_scryfall_cards(client, scryfall_query)

        if not cards and scryfall_query != query_name:
            cards = await _fetch_scryfall_cards(client, query_name)

    ranked = sorted(
        cards,
        key=lambda card: (
            -_score_magic_candidate(card, extracted),
            card.get("name") or "",
        ),
    )

    return [_map_magic_card(card) for card in ranked[: config.MAX_CANDIDATES]]


def _normalize_search_text(value: str) -> str:
    import unicodedata

    return (
        unicodedata.normalize("NFD", value.lower())
        .encode("ascii", "ignore")
        .decode("ascii")
        .replace("/", " ")
        .replace("-", " ")
        .strip()
    )


def _rank_name_match(name: str, query: str) -> int:
    normalized_name = _normalize_search_text(name)
    normalized_query = _normalize_search_text(query)

    if normalized_name == normalized_query:
        return 0

    if normalized_name.startswith(normalized_query):
        return 1

    return 2


def _format_riftbound_number(collector_number: int, riftbound_id: str) -> str:
    parts = riftbound_id.split("-")
    set_total = parts[-1] if parts else None

    if set_total and set_total.isdigit():
        return f"#{collector_number}/{set_total}"

    return f"#{collector_number}"


def _format_riftbound_type(card: dict) -> str:
    classification = card.get("classification") or {}
    card_type = classification.get("type") or ""
    supertype = classification.get("supertype") or ""
    domain = classification.get("domain") or []
    domain_label = " · ".join(domain) if domain else ""
    type_label = f"{supertype} · {card_type}" if supertype else card_type

    if domain_label:
        return f"{type_label} · {domain_label}"

    return type_label


def _map_riftbound_card(card: dict) -> ScannedCardResponse:
    card_set = card.get("set") or {}
    media = card.get("media") or {}
    classification = card.get("classification") or {}

    return ScannedCardResponse(
        id=card.get("riftbound_id") or card.get("id") or "",
        name=card.get("name") or "",
        setName=card_set.get("label") or "",
        number=_format_riftbound_number(
            int(card.get("collector_number") or 0),
            str(card.get("riftbound_id") or ""),
        ),
        type=_format_riftbound_type(card),
        imageUrl=media.get("image_url") or "",
        accentColor=RIFTBOUND_ACCENT_COLOR,
        rarity=classification.get("rarity"),
    )


async def search_riftbound_candidates(detected_name: str) -> list[ScannedCardResponse]:
    query = detected_name.strip()

    if not query:
        return []

    all_cards: list[dict] = []

    async with httpx.AsyncClient(timeout=TCG_API_TIMEOUT) as client:
        for page in range(1, RIFTCODEX_MAX_SEARCH_PAGES + 1):
            params = {
                "fuzzy": query,
                "page": str(page),
                "size": str(RIFTCODEX_SEARCH_PAGE_SIZE),
                "sort": "set_id",
                "dir": "-1",
            }
            response = await client.get(
                f"{config.RIFTCODEX_BASE_URL}/cards/name",
                params=params,
            )
            response.raise_for_status()
            payload = response.json()
            items = payload.get("items") or []

            if not isinstance(items, list):
                break

            all_cards.extend(items)

            pages = payload.get("pages") or page
            if len(items) < RIFTCODEX_SEARCH_PAGE_SIZE or page >= pages:
                break

    ranked = sorted(
        all_cards,
        key=lambda card: (
            _rank_name_match(str(card.get("name") or ""), query),
            str(card.get("name") or ""),
        ),
    )

    return [_map_riftbound_card(card) for card in ranked[: config.MAX_CANDIDATES]]
