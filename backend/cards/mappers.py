import config
from cards.constants import PT_TYPE_TO_EN, TYPE_ACCENT_COLORS
from models import ExtractedCardInfo, ScannedCardResponse


def format_card_number(number: str, set_total: int) -> str:
    return f"#{number}/{set_total}"


def get_card_type(types: list[str] | None) -> str:
    return types[0] if types else "Unknown"


def get_accent_color(card_type: str) -> str:
    return TYPE_ACCENT_COLORS.get(card_type, "#6C63FF")


def _tcgplayer_market_price(tcgplayer: dict) -> float | None:
    for value in tcgplayer.values():
        if not isinstance(value, dict):
            continue
        market_price = value.get("marketPrice")
        if isinstance(market_price, (int, float)) and market_price > 0:
            return float(market_price)
    for value in tcgplayer.values():
        if not isinstance(value, dict):
            continue
        mid_price = value.get("midPrice")
        if isinstance(mid_price, (int, float)) and mid_price > 0:
            return float(mid_price)
    return None


def pricing_to_estimated_brl(pricing: dict | None) -> float | None:
    if not pricing:
        return None

    cardmarket = pricing.get("cardmarket") or {}
    market_eur = cardmarket.get("trend") or cardmarket.get("avg") or cardmarket.get("low")
    if isinstance(market_eur, (int, float)) and market_eur > 0:
        return round(float(market_eur) * config.EUR_TO_BRL, 2)

    tcgplayer = pricing.get("tcgplayer")
    if isinstance(tcgplayer, dict):
        market_usd = _tcgplayer_market_price(tcgplayer)
        if market_usd is not None:
            return round(market_usd * config.USD_TO_BRL, 2)

    return None


def map_tcgdex_card(card: dict) -> ScannedCardResponse:
    types = card.get("types") or []
    type_name = types[0] if types else "Unknown"
    type_for_color = PT_TYPE_TO_EN.get(type_name, type_name)
    set_data = card.get("set") or {}
    card_count = set_data.get("cardCount") or {}
    set_total = card_count.get("official") or card_count.get("total") or 0
    local_id = str(card.get("localId") or "?")
    image_base = card.get("image") or ""

    return ScannedCardResponse(
        id=f"tcgdex-{card['id']}",
        name=card["name"],
        setName=set_data.get("name", "Unknown"),
        number=format_card_number(local_id, set_total),
        type=type_name,
        imageUrl=f"{image_base}/high.webp" if image_base else "",
        accentColor=get_accent_color(type_for_color),
        rarity=card.get("rarity"),
        estimatedValueBrl=pricing_to_estimated_brl(card.get("pricing")),
    )


def map_tcg_card(card: dict) -> ScannedCardResponse:
    card_type = get_card_type(card.get("types"))
    set_data = card.get("set") or {}
    images = card.get("images") or {}

    return ScannedCardResponse(
        id=card["id"],
        name=card["name"],
        setName=set_data.get("name", "Unknown"),
        number=format_card_number(card["number"], set_data.get("total", 0)),
        type=card_type,
        imageUrl=images.get("large") or images.get("small") or "",
        accentColor=get_accent_color(card_type),
        rarity=card.get("rarity"),
    )


def get_search_names(extracted: ExtractedCardInfo) -> list[str]:
    names: list[str] = []
    for value in (extracted.name, extracted.nameEnglish):
        cleaned = (value or "").strip()
        if cleaned and cleaned not in names:
            names.append(cleaned)
    return names


def local_id_variants(number: str | None) -> list[str]:
    if not number:
        return []

    variants: list[str] = []
    for value in (number, number.lstrip("0") or "0", number.zfill(3)):
        if value not in variants:
            variants.append(value)
    return variants


def resolve_tcgdex_lang(language: str | None) -> str:
    normalized = (language or "").lower()
    if any(token in normalized for token in ("portug", "brasil", "brazil")):
        return "pt"
    if "english" in normalized or "ingl" in normalized:
        return "en"
    if "spanish" in normalized or "espan" in normalized:
        return "es"
    return "pt"
