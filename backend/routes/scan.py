import logging

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from cards.search import search_candidates
from models import ScanCardResponse, ScannedCardResponse
from utils.games import normalize_game_type
from utils.images import detect_image_mime_type
from vision.service import analyze_card_image

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scan"])

MAX_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("/scan-card", response_model=ScanCardResponse)
async def scan_card(
    image: UploadFile = File(...),
    game_type: str = Form(default="pokemon"),
) -> ScanCardResponse:
    normalized_game_type = normalize_game_type(game_type)
    image_bytes = await image.read()

    if len(image_bytes) == 0:
        raise HTTPException(status_code=400, detail="A imagem enviada está vazia.")

    mime_type = detect_image_mime_type(image_bytes)
    declared_type = image.content_type or ""

    if (
        declared_type
        and not declared_type.startswith("image/")
        and mime_type == "application/octet-stream"
    ):
        raise HTTPException(status_code=400, detail="Envie um arquivo de imagem válido.")

    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(status_code=400, detail="A imagem deve ter no máximo 10 MB.")

    extracted, confidence = analyze_card_image(image_bytes, normalized_game_type)

    candidates: list[ScannedCardResponse]
    if normalized_game_type in {"riftbound", "magic", "onepiece"}:
        candidates = []
    else:
        candidates = await search_candidates(extracted)

    if not extracted.name and confidence != "low":
        confidence = "low"

    logger.info(
        "[scan-card] game=%s confidence=%s extracted=%s candidates=%s",
        normalized_game_type,
        confidence,
        extracted.model_dump(),
        len(candidates),
    )

    return ScanCardResponse(
        confidence=confidence,
        extracted=extracted,
        candidates=candidates,
    )
