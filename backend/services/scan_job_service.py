import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

import config
from cards.magic_riftbound_search import search_magic_candidates, search_riftbound_candidates
from cards.search import search_candidates
from models import ExtractedCardInfo, GameType, ScannedCardResponse
from utils.supabase_client import get_supabase_client
from vision.service import analyze_card_image

logger = logging.getLogger(__name__)

IMAGE_DOWNLOAD_TIMEOUT = httpx.Timeout(15.0, read=30.0)


def _row_to_dict(row: dict[str, Any]) -> dict[str, Any]:
    return dict(row)


def create_scan_job_record(
    *,
    user_id: str,
    game_type: GameType,
    image_url: str,
    job_id: str | None = None,
) -> dict[str, Any]:
    client = get_supabase_client()
    resolved_job_id = job_id or str(uuid.uuid4())
    payload = {
        "id": resolved_job_id,
        "user_id": user_id,
        "game_type": game_type,
        "image_url": image_url,
        "status": "pending",
    }
    response = client.table("scan_jobs").insert(payload).execute()
    rows = response.data or []

    if not rows:
        raise RuntimeError("Não foi possível criar o job de scan.")

    return _row_to_dict(rows[0])


def upload_scan_image(
    *,
    user_id: str,
    job_id: str,
    image_bytes: bytes,
    mime_type: str,
) -> str:
    client = get_supabase_client()
    extension = "jpg" if mime_type == "image/jpeg" else "png"
    storage_path = f"{user_id}/{job_id}.{extension}"

    client.storage.from_(config.SUPABASE_STORAGE_BUCKET).upload(
        storage_path,
        image_bytes,
        {"content-type": mime_type, "upsert": "true"},
    )

    public_url = client.storage.from_(config.SUPABASE_STORAGE_BUCKET).get_public_url(
        storage_path
    )
    return public_url


def get_scan_job(job_id: str, user_id: str) -> dict[str, Any] | None:
    client = get_supabase_client()
    response = (
        client.table("scan_jobs")
        .select("*")
        .eq("id", job_id)
        .eq("user_id", user_id)
        .limit(1)
        .execute()
    )
    rows = response.data or []

    if not rows:
        return None

    return _row_to_dict(rows[0])


def list_active_scan_jobs(user_id: str) -> list[dict[str, Any]]:
    client = get_supabase_client()
    active_response = (
        client.table("scan_jobs")
        .select("*")
        .eq("user_id", user_id)
        .is_("confirmed_at", "null")
        .in_("status", ["pending", "processing"])
        .order("created_at", desc=True)
        .execute()
    )
    active_rows = [_row_to_dict(row) for row in (active_response.data or [])]

    cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    completed_response = (
        client.table("scan_jobs")
        .select("*")
        .eq("user_id", user_id)
        .is_("confirmed_at", "null")
        .eq("status", "completed")
        .gte("updated_at", cutoff)
        .order("updated_at", desc=True)
        .execute()
    )
    completed_rows = [_row_to_dict(row) for row in (completed_response.data or [])]

    seen_ids = {row["id"] for row in active_rows}
    merged = active_rows + [row for row in completed_rows if row["id"] not in seen_ids]
    return merged


def confirm_scan_job(job_id: str, user_id: str) -> bool:
    row = get_scan_job(job_id, user_id)

    if row is None:
        return False

    update_scan_job(job_id, confirmed_at=datetime.now(timezone.utc).isoformat())
    return True


def update_scan_job(job_id: str, **fields: Any) -> None:
    client = get_supabase_client()
    client.table("scan_jobs").update(fields).eq("id", job_id).execute()


def _download_image(image_url: str) -> bytes:
    with httpx.Client(timeout=IMAGE_DOWNLOAD_TIMEOUT) as client:
        response = client.get(image_url)
        response.raise_for_status()
        return response.content


async def _search_candidates_for_game(
    game_type: GameType,
    extracted: ExtractedCardInfo,
    detected_name: str,
) -> list[ScannedCardResponse]:
    if game_type == "pokemon":
        return await search_candidates(extracted)

    if game_type == "magic":
        return await search_magic_candidates(extracted, detected_name)

    if game_type == "riftbound":
        return await search_riftbound_candidates(detected_name)

    return []


def process_scan_job(job_id: str) -> None:
    """RQ worker entrypoint — processes a scan job by id."""
    client = get_supabase_client()
    response = client.table("scan_jobs").select("*").eq("id", job_id).limit(1).execute()
    rows = response.data or []

    if not rows:
        logger.error("[scan-job] job not found: %s", job_id)
        return

    job = _row_to_dict(rows[0])
    game_type: GameType = job["game_type"]

    update_scan_job(job_id, status="processing")

    try:
        image_bytes = _download_image(job["image_url"])
        extracted, _confidence = analyze_card_image(image_bytes, game_type)
        detected_name = (
            (extracted.name or "").strip()
            or (extracted.nameEnglish or "").strip()
            or None
        )

        candidates = asyncio.run(
            _search_candidates_for_game(game_type, extracted, detected_name or "")
        )

        update_scan_job(
            job_id,
            status="completed",
            detected_name=detected_name,
            result_candidates=[candidate.model_dump() for candidate in candidates],
            error_message=None,
        )

        logger.info(
            "[scan-job] completed job=%s game=%s detected=%s candidates=%s",
            job_id,
            game_type,
            detected_name,
            len(candidates),
        )
    except Exception as exc:
        logger.exception("[scan-job] failed job=%s", job_id)
        update_scan_job(
            job_id,
            status="failed",
            error_message=str(exc) or "Erro desconhecido ao processar o scan.",
        )
