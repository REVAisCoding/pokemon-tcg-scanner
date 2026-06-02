import logging
import re

import httpx
from fastapi import HTTPException

import config
from pricing.riftcodex import fetch_tcgplayer_id_by_riftbound_id
from pricing.tcgplayer_public import fetch_tcgplayer_public_price

logger = logging.getLogger(__name__)


def _normalize_label(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


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


def _extract_price_from_card_payload(data: dict[str, object]) -> dict[str, object] | None:
    prices = data.get("prices")
    if isinstance(prices, list) and prices:
        return extract_tcgapi_dev_price(prices)

    for field in ("market_price", "foil_market_price"):
        value = data.get(field)
        if isinstance(value, (int, float)) and value > 0:
            return {
                "amount": float(value),
                "currency": "USD",
                "source": "tcgplayer",
                "updatedAt": data.get("last_updated_at"),
            }

    return None


def _score_search_match(
    card: dict[str, object],
    *,
    name: str,
    set_id: str | None,
) -> int:
    score = 0
    card_name = card.get("name")
    normalized_name = _normalize_label(name)
    normalized_card_name = _normalize_label(str(card_name)) if isinstance(card_name, str) else ""

    if normalized_card_name == normalized_name:
        score += 100
    elif normalized_name and normalized_name in normalized_card_name:
        score += 60
    elif normalized_card_name and normalized_card_name in normalized_name:
        score += 40

    if set_id:
        set_slug = card.get("set_slug")
        set_name = card.get("set_name")
        normalized_set_id = _normalize_label(set_id)

        if isinstance(set_slug, str) and _normalize_label(set_slug) == normalized_set_id:
            score += 80
        elif isinstance(set_name, str) and normalized_set_id in _normalize_label(set_name):
            score += 40

    return score


def _require_tcgapi_dev_key() -> None:
    if not config.is_tcgapi_dev_configured():
        raise HTTPException(
            status_code=503,
            detail=(
                "TCGAPI_DEV_KEY não configurada. Crie uma chave gratuita em "
                "https://tcgapi.dev e adicione ao backend/.env"
            ),
        )


async def _fetch_tcgapi_json(path: str, *, params: dict[str, str | int] | None = None) -> dict[str, object]:
    _require_tcgapi_dev_key()

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{config.TCGAPI_DEV_BASE_URL}{path}",
                headers={"X-API-Key": config.TCGAPI_DEV_KEY},
                params=params,
            )
    except httpx.HTTPError as exc:
        logger.exception("TCG API request failed for path=%s", path)
        raise HTTPException(
            status_code=502,
            detail="Não foi possível consultar o preço da carta.",
        ) from exc

    if response.status_code == 404:
        return {}

    if response.status_code >= 400:
        logger.warning(
            "TCG API error for path=%s status=%s body=%s",
            path,
            response.status_code,
            response.text[:300],
        )
        raise HTTPException(status_code=502, detail="Não foi possível consultar o preço da carta.")

    payload = response.json()
    return payload if isinstance(payload, dict) else {}


async def _fetch_riftbound_price_via_tcgapi(tcgplayer_id: str) -> dict[str, object] | None:
    if not config.is_tcgapi_dev_configured():
        return None

    payload = await _fetch_tcgapi_json(f"/cards/tcgplayer/{tcgplayer_id}")
    data = payload.get("data")

    if not isinstance(data, dict):
        return None

    return _extract_price_from_card_payload(data)


async def fetch_riftbound_price(tcgplayer_id: str) -> dict[str, object] | None:
    normalized_id = tcgplayer_id.strip()

    if not normalized_id.isdigit():
        raise HTTPException(status_code=400, detail="ID do TCGPlayer inválido.")

    price = await _fetch_riftbound_price_via_tcgapi(normalized_id)
    if price:
        return price

    return await fetch_tcgplayer_public_price(normalized_id)


async def fetch_riftbound_price_by_search(
    name: str,
    *,
    set_id: str | None = None,
) -> dict[str, object] | None:
    normalized_name = name.strip()

    if len(normalized_name) < 2:
        return None

    if not config.is_tcgapi_dev_configured():
        return None

    payload = await _fetch_tcgapi_json(
        "/search",
        params={
            "q": normalized_name,
            "game": config.RIFTBOUND_TCGAPI_GAME_SLUG,
            "per_page": 10,
        },
    )
    data = payload.get("data")

    if not isinstance(data, list) or not data:
        return None

    ranked_cards = sorted(
        (card for card in data if isinstance(card, dict)),
        key=lambda card: _score_search_match(card, name=normalized_name, set_id=set_id),
        reverse=True,
    )

    for card in ranked_cards:
        direct_price = _extract_price_from_card_payload(card)
        if direct_price:
            return direct_price

        tcgplayer_id = card.get("tcgplayer_id")
        if isinstance(tcgplayer_id, int):
            price = await fetch_riftbound_price(str(tcgplayer_id))
            if price:
                return price

        card_id = card.get("id")
        if isinstance(card_id, int):
            prices_payload = await _fetch_tcgapi_json(f"/cards/{card_id}/prices")
            prices_data = prices_payload.get("data")
            if isinstance(prices_data, list):
                price = extract_tcgapi_dev_price(prices_data)
                if price:
                    return price

    return None


async def fetch_riftbound_price_for_card(
    *,
    tcgplayer_id: str | None = None,
    riftbound_id: str | None = None,
    name: str | None = None,
    set_id: str | None = None,
) -> dict[str, object] | None:
    resolved_tcgplayer_id = tcgplayer_id.strip() if tcgplayer_id and tcgplayer_id.strip().isdigit() else None

    if not resolved_tcgplayer_id and riftbound_id and riftbound_id.strip():
        resolved_tcgplayer_id = await fetch_tcgplayer_id_by_riftbound_id(riftbound_id)

    if resolved_tcgplayer_id:
        price = await _fetch_riftbound_price_via_tcgapi(resolved_tcgplayer_id)
        if price:
            return price

        public_price = await fetch_tcgplayer_public_price(resolved_tcgplayer_id)
        if public_price:
            return public_price

    if name and name.strip():
        price = await fetch_riftbound_price_by_search(name.strip(), set_id=set_id)
        if price:
            return price

    return None
