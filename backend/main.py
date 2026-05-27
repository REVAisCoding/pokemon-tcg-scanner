import base64
import json
import logging
import os
import re
from typing import Literal

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI, RateLimitError
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Pokemon Card Scan API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

API_BASE_URL = "https://api.pokemontcg.io/v2"
TCGDEX_BASE_URL = "https://api.tcgdex.net/v2"
EUR_TO_BRL = 6.35
USD_TO_BRL = 5.75
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
POKEMON_TCG_API_KEY = os.getenv("POKEMON_TCG_API_KEY")

PT_TYPE_TO_EN: dict[str, str] = {
    "Dragão": "Dragon",
    "Elétrico": "Lightning",
    "Fada": "Fairy",
    "Fogo": "Fire",
    "Incolor": "Colorless",
    "Lutador": "Fighting",
    "Metal": "Metal",
    "Planta": "Grass",
    "Psíquico": "Psychic",
    "Sombrio": "Darkness",
    "Água": "Water",
}

TYPE_ACCENT_COLORS: dict[str, str] = {
    "Colorless": "#A8A878",
    "Darkness": "#705848",
    "Dragon": "#7038F8",
    "Fairy": "#EE99AC",
    "Fighting": "#C03028",
    "Fire": "#F08030",
    "Grass": "#78C850",
    "Lightning": "#F7D046",
    "Metal": "#B8B8D0",
    "Psychic": "#F85888",
    "Water": "#6890F0",
}

VISION_PROMPT = """Analyze this Pokémon trading card image and extract visible card information.

Return JSON with exactly these fields:
{
  "name": "card name in the language printed on the card, or null if unreadable",
  "nameEnglish": "official English Pokémon name for API lookup (same as name if already English)",
  "number": "collector number only (e.g. '58' from '58/102'), or null",
  "set": "set/expansion name if visible, or null",
  "language": "language of the card text (e.g. 'Portuguese', 'English', 'Japanese'), or null",
  "confidence": "high, medium, or low — how confident you are in the name extraction"
}

Rules:
- Use the exact name as printed on the card.
- Always provide nameEnglish: translate the Pokémon name to English when the card is not in English.
  Examples: 'Rato' -> 'Rattata', 'Pikachu' -> 'Pikachu', 'Charizard' -> 'Charizard'.
- For number, return only the first part before the slash.
- confidence=low if the image is blurry, cropped, or the name is unclear.
- confidence=medium if you can read the name but set/number are uncertain.
- confidence=high if name is clearly readable and matches typical card layout.
- Return only valid JSON, no markdown."""


class ExtractedCardInfo(BaseModel):
    name: str | None = None
    nameEnglish: str | None = None
    number: str | None = None
    set: str | None = None
    language: str | None = None


class ScannedCardResponse(BaseModel):
    id: str
    name: str
    setName: str
    number: str
    type: str
    imageUrl: str
    accentColor: str
    rarity: str | None = None
    estimatedValueBrl: float | None = None


class ScanCardResponse(BaseModel):
    confidence: Literal["high", "medium", "low"]
    extracted: ExtractedCardInfo
    candidates: list[ScannedCardResponse]


def is_openai_key_configured() -> bool:
    key = (OPENAI_API_KEY or "").strip()
    if not key:
        return False
    if key in {"sk-your-openai-key", "your-openai-key", "changeme"}:
        return False
    return key.startswith("sk-")


def get_openai_client() -> OpenAI:
    if not is_openai_key_configured():
        raise HTTPException(
            status_code=500,
            detail=(
                "OPENAI_API_KEY não configurada. Edite backend/.env com sua chave "
                "de https://platform.openai.com/api-keys e reinicie o backend."
            ),
        )
    return OpenAI(api_key=OPENAI_API_KEY)


def normalize_confidence(value: str | None) -> Literal["high", "medium", "low"]:
    normalized = (value or "low").strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized  # type: ignore[return-value]
    return "low"


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
        return round(float(market_eur) * EUR_TO_BRL, 2)

    tcgplayer = pricing.get("tcgplayer")
    if isinstance(tcgplayer, dict):
        market_usd = _tcgplayer_market_price(tcgplayer)
        if market_usd is not None:
            return round(market_usd * USD_TO_BRL, 2)

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


def resolve_tcgdex_lang(language: str | None) -> str:
    normalized = (language or "").lower()
    if any(token in normalized for token in ("portug", "brasil", "brazil")):
        return "pt"
    if "english" in normalized or "ingl" in normalized:
        return "en"
    if "spanish" in normalized or "espan" in normalized:
        return "es"
    return "pt"


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


TCG_API_TIMEOUT = httpx.Timeout(10.0, read=60.0)
MAX_CANDIDATES = 3


def escape_query_value(value: str) -> str:
    return value.replace('"', '\\"')


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


async def fetch_tcgdex_card_list(
    client: httpx.AsyncClient,
    lang: str,
    params: dict[str, str],
) -> list[dict]:
    try:
        response = await client.get(f"{TCGDEX_BASE_URL}/{lang}/cards", params=params)
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
        response = await client.get(f"{TCGDEX_BASE_URL}/{lang}/cards/{card_id}")
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

    brief_cards: list[dict] = []
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
                        brief_cards.append(match)

        if len(brief_cards) >= MAX_CANDIDATES:
            break

        matches = await fetch_tcgdex_card_list(client, lang, {"name": name})
        for match in matches:
            if match["id"] not in seen_brief_ids:
                seen_brief_ids.add(match["id"])
                brief_cards.append(match)

        if len(brief_cards) >= MAX_CANDIDATES:
            break

    candidates: list[ScannedCardResponse] = []
    for brief in brief_cards:
        detail = await fetch_tcgdex_card_detail(client, lang, brief["id"])
        if not detail:
            continue
        candidates.append(map_tcgdex_card(detail))
        if len(candidates) >= MAX_CANDIDATES:
            break

    return candidates


async def search_pokemontcg_candidates(
    client: httpx.AsyncClient,
    extracted: ExtractedCardInfo,
) -> list[ScannedCardResponse]:
    search_extracted = extracted
    if extracted.nameEnglish:
        search_extracted = extracted.model_copy(update={"name": extracted.nameEnglish})

    seen_ids: set[str] = set()
    candidates: list[ScannedCardResponse] = []
    queries = build_search_queries(search_extracted)

    for query in queries:
        cards = await fetch_tcg_cards(client, query)
        for card in cards:
            mapped = map_tcg_card(card)
            if mapped.id in seen_ids:
                continue
            seen_ids.add(mapped.id)
            candidates.append(mapped)
            if len(candidates) >= MAX_CANDIDATES:
                return candidates

    return candidates


async def fetch_tcg_cards(
    client: httpx.AsyncClient,
    query: str,
    page_size: int = MAX_CANDIDATES,
) -> list[dict]:
    try:
        response = await client.get(
            f"{API_BASE_URL}/cards",
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


async def search_candidates(extracted: ExtractedCardInfo) -> list[ScannedCardResponse]:
    seen_ids: set[str] = set()
    candidates: list[ScannedCardResponse] = []
    lang = resolve_tcgdex_lang(extracted.language)

    headers: dict[str, str] = {}
    if POKEMON_TCG_API_KEY:
        headers["X-Api-Key"] = POKEMON_TCG_API_KEY

    async with httpx.AsyncClient(timeout=TCG_API_TIMEOUT, headers=headers) as client:
        tcgdex_results = await search_tcgdex_candidates(client, extracted, lang)
        for card in tcgdex_results:
            if card.id in seen_ids:
                continue
            seen_ids.add(card.id)
            candidates.append(card)

        if len(candidates) < MAX_CANDIDATES:
            pokemon_results = await search_pokemontcg_candidates(client, extracted)
            for card in pokemon_results:
                if card.id in seen_ids:
                    continue
                seen_ids.add(card.id)
                candidates.append(card)
                if len(candidates) >= MAX_CANDIDATES:
                    break

    return candidates[:MAX_CANDIDATES]


def detect_image_mime_type(image_bytes: bytes) -> str:
    if image_bytes.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if image_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if image_bytes.startswith(b"RIFF") and image_bytes[8:12] == b"WEBP":
        return "image/webp"
    if image_bytes[4:8] == b"ftyp":
        return "image/heic"
    return "application/octet-stream"


def raise_openai_error(exc: Exception) -> None:
    logger.exception("OpenAI vision request failed")

    if isinstance(exc, AuthenticationError):
        raise HTTPException(
            status_code=500,
            detail="Chave da OpenAI inválida. Verifique OPENAI_API_KEY em backend/.env.",
        ) from exc

    if isinstance(exc, RateLimitError):
        message = str(exc).lower()
        if "insufficient_quota" in message or "exceeded your current quota" in message:
            raise HTTPException(
                status_code=402,
                detail=(
                    "Créditos da OpenAI esgotados. Adicione saldo em "
                    "https://platform.openai.com/settings/organization/billing"
                ),
            ) from exc

        raise HTTPException(
            status_code=429,
            detail="Limite de requisições da OpenAI atingido. Tente novamente em instantes.",
        ) from exc

    if isinstance(exc, APIConnectionError):
        raise HTTPException(
            status_code=503,
            detail="Não foi possível conectar à OpenAI. Verifique sua internet e tente novamente.",
        ) from exc

    if isinstance(exc, APIStatusError):
        raise HTTPException(
            status_code=502,
            detail=f"Erro na OpenAI ({exc.status_code}). Tente novamente.",
        ) from exc

    raise HTTPException(
        status_code=502,
        detail="Não foi possível analisar a imagem da carta.",
    ) from exc


def analyze_card_image(image_bytes: bytes) -> tuple[ExtractedCardInfo, Literal["high", "medium", "low"]]:
    client = get_openai_client()
    mime_type = detect_image_mime_type(image_bytes)

    if mime_type == "image/heic":
        raise HTTPException(
            status_code=400,
            detail="Formato HEIC não suportado. Tire a foto novamente em JPEG.",
        )

    if mime_type == "application/octet-stream":
        raise HTTPException(
            status_code=400,
            detail="Formato de imagem não reconhecido. Use JPEG ou PNG.",
        )

    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{mime_type};base64,{base64_image}",
                            },
                        },
                    ],
                }
            ],
            response_format={"type": "json_object"},
            max_tokens=400,
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise_openai_error(exc)

    content = response.choices[0].message.content or "{}"

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Resposta inválida do serviço de visão.",
        ) from exc

    extracted = ExtractedCardInfo(
        name=_clean_text(parsed.get("name")),
        nameEnglish=_clean_text(parsed.get("nameEnglish")),
        number=_clean_number(parsed.get("number")),
        set=_clean_text(parsed.get("set")),
        language=_clean_text(parsed.get("language")),
    )
    confidence = normalize_confidence(parsed.get("confidence"))

    return extracted, confidence


def _clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "unknown", "n/a"}:
        return None
    return text


def _clean_number(value: object) -> str | None:
    text = _clean_text(value)
    if not text:
        return None
    match = re.search(r"\d+", text)
    return match.group(0) if match else None


@app.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "openai_configured": is_openai_key_configured(),
    }


@app.post("/scan-card", response_model=ScanCardResponse)
async def scan_card(image: UploadFile = File(...)) -> ScanCardResponse:
    image_bytes = await image.read()

    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="A imagem enviada está vazia.")

    mime_type = detect_image_mime_type(image_bytes)
    declared_type = image.content_type or ""

    if declared_type and not declared_type.startswith("image/") and mime_type == "application/octet-stream":
        raise HTTPException(status_code=400, detail="Envie um arquivo de imagem válido.")

    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="A imagem deve ter no máximo 10 MB.")

    extracted, confidence = analyze_card_image(image_bytes)

    candidates = await search_candidates(extracted)

    if not extracted.name and confidence != "low":
        confidence = "low"

    print(
        f"[scan-card] confidence={confidence} extracted={extracted.model_dump()} "
        f"candidates={len(candidates)}"
    )

    return ScanCardResponse(
        confidence=confidence,
        extracted=extracted,
        candidates=candidates,
    )
