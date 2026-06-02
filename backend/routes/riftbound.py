from fastapi import APIRouter

from pricing.tcgapi_dev import fetch_riftbound_price

router = APIRouter(tags=["riftbound"])


@router.get("/riftbound/price/{tcgplayer_id}")
async def get_riftbound_price(tcgplayer_id: str) -> dict[str, dict[str, object] | None]:
    price = await fetch_riftbound_price(tcgplayer_id)
    return {"price": price}
