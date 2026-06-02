import config
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str | bool]:
    return {
        "status": "ok",
        "openai_configured": config.is_openai_key_configured(),
        "tcgapi_dev_configured": config.is_tcgapi_dev_configured(),
    }
