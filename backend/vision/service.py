import base64
import json
import logging

from fastapi import HTTPException
from openai import APIConnectionError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

import config
from models import ConfidenceLevel, ExtractedCardInfo, GameType
from utils.images import detect_image_mime_type
from utils.text import clean_number, clean_text, normalize_confidence
from vision.prompts import get_vision_prompt

logger = logging.getLogger(__name__)


def get_openai_client() -> OpenAI:
    if not config.is_openai_key_configured():
        raise HTTPException(
            status_code=500,
            detail=(
                "OPENAI_API_KEY não configurada. Edite backend/.env com sua chave "
                "de https://platform.openai.com/api-keys e reinicie o backend."
            ),
        )
    return OpenAI(api_key=config.OPENAI_API_KEY)


def _raise_openai_error(exc: Exception) -> None:
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


def _validate_image_mime_type(mime_type: str) -> None:
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


def _call_vision_model(
    client: OpenAI,
    image_bytes: bytes,
    mime_type: str,
    game_type: GameType,
) -> dict[str, object]:
    base64_image = base64.b64encode(image_bytes).decode("utf-8")

    try:
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": get_vision_prompt(game_type)},
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
        _raise_openai_error(exc)

    content = response.choices[0].message.content or "{}"

    try:
        parsed = json.loads(content)
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=502,
            detail="Resposta inválida do serviço de visão.",
        ) from exc

    return parsed if isinstance(parsed, dict) else {}


def _parse_vision_response(parsed: dict[str, object]) -> tuple[ExtractedCardInfo, ConfidenceLevel]:
    extracted = ExtractedCardInfo(
        name=clean_text(parsed.get("name")),
        nameEnglish=clean_text(parsed.get("nameEnglish")),
        number=clean_number(parsed.get("number")),
        set=clean_text(parsed.get("set")),
        language=clean_text(parsed.get("language")),
    )
    confidence = normalize_confidence(
        parsed.get("confidence") if isinstance(parsed.get("confidence"), str) else None
    )
    return extracted, confidence


def analyze_card_image(
    image_bytes: bytes,
    game_type: GameType = "pokemon",
) -> tuple[ExtractedCardInfo, ConfidenceLevel]:
    mime_type = detect_image_mime_type(image_bytes)
    _validate_image_mime_type(mime_type)

    client = get_openai_client()
    parsed = _call_vision_model(client, image_bytes, mime_type, game_type)
    return _parse_vision_response(parsed)
