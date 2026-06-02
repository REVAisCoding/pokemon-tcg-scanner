import logging
import uuid
from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile

from models import ScanJobCreateResponse, ScanJobResponse, ScannedCardResponse
from services.queue import get_scan_queue
from services.scan_job_service import (
    confirm_scan_job,
    create_scan_job_record,
    get_scan_job,
    list_active_scan_jobs,
    process_scan_job,
    upload_scan_image,
)
from utils.auth import get_current_user_id
from utils.games import normalize_game_type
from utils.images import detect_image_mime_type

import config

logger = logging.getLogger(__name__)

router = APIRouter(tags=["scan-jobs"])

MAX_IMAGE_BYTES = 10 * 1024 * 1024


def _require_async_scan_configured() -> None:
    if not config.is_supabase_configured():
        raise HTTPException(
            status_code=503,
            detail="Scan assíncrono não configurado (Supabase).",
        )

    if not config.is_redis_configured():
        raise HTTPException(
            status_code=503,
            detail="Scan assíncrono não configurado (Redis).",
        )


def _parse_candidates(raw: Any) -> list[ScannedCardResponse] | None:
    if raw is None:
        return None

    if not isinstance(raw, list):
        return None

    candidates: list[ScannedCardResponse] = []

    for item in raw:
        if isinstance(item, dict):
            candidates.append(ScannedCardResponse.model_validate(item))

    return candidates


def _to_response(row: dict[str, Any]) -> ScanJobResponse:
    status = row.get("status")
    candidates = _parse_candidates(row.get("result_candidates"))

    return ScanJobResponse(
        id=row["id"],
        status=status,
        gameType=row["game_type"],
        imageUrl=row.get("image_url"),
        detectedName=row.get("detected_name"),
        resultCandidates=candidates if status == "completed" else None,
        errorMessage=row.get("error_message") if status == "failed" else None,
        createdAt=row.get("created_at") or "",
        updatedAt=row.get("updated_at") or "",
    )


@router.post("/scan-jobs", response_model=ScanJobCreateResponse)
async def create_scan_job(
    image: UploadFile = File(...),
    game_type: str = Form(default="pokemon"),
    user_id: str = Depends(get_current_user_id),
) -> ScanJobCreateResponse:
    _require_async_scan_configured()

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

    job_id = str(uuid.uuid4())

    try:
        image_url = upload_scan_image(
            user_id=user_id,
            job_id=job_id,
            image_bytes=image_bytes,
            mime_type=mime_type,
        )
        job = create_scan_job_record(
            user_id=user_id,
            game_type=normalized_game_type,
            image_url=image_url,
            job_id=job_id,
        )
    except Exception as exc:
        logger.exception("[scan-jobs] failed to upload image job=%s", job_id)
        raise HTTPException(status_code=500, detail="Não foi possível salvar a imagem.") from exc

    queue = get_scan_queue()
    queue.enqueue(process_scan_job, job_id, job_timeout="5m")

    logger.info("[scan-jobs] enqueued job=%s user=%s game=%s", job_id, user_id, normalized_game_type)

    return ScanJobCreateResponse(jobId=job_id)


@router.get("/scan-jobs", response_model=list[ScanJobResponse])
async def list_scan_jobs(
    user_id: str = Depends(get_current_user_id),
) -> list[ScanJobResponse]:
    _require_async_scan_configured()

    rows = list_active_scan_jobs(user_id)
    return [_to_response(row) for row in rows]


@router.get("/scan-jobs/{job_id}", response_model=ScanJobResponse)
async def get_scan_job_status(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
) -> ScanJobResponse:
    _require_async_scan_configured()

    row = get_scan_job(job_id, user_id)

    if row is None:
        raise HTTPException(status_code=404, detail="Job de scan não encontrado.")

    return _to_response(row)


@router.post("/scan-jobs/{job_id}/confirm")
async def confirm_scan_job_route(
    job_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, bool]:
    _require_async_scan_configured()

    if not confirm_scan_job(job_id, user_id):
        raise HTTPException(status_code=404, detail="Job de scan não encontrado.")

    return {"ok": True}
