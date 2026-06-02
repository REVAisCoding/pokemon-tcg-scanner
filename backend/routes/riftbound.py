from fastapi import APIRouter, HTTPException, Query

from pricing.tcgapi_dev import fetch_riftbound_price_for_card

router = APIRouter(tags=["riftbound"])


@router.get("/riftbound/price/by-id/{riftbound_id}")
async def get_riftbound_price_by_id(
    riftbound_id: str,
    tcgplayer_id: str | None = Query(default=None),
    name: str | None = Query(default=None),
    set_id: str | None = Query(default=None),
) -> dict[str, dict[str, object] | None]:
    normalized_id = riftbound_id.strip()

    if not normalized_id:
        raise HTTPException(status_code=400, detail="ID Riftbound inválido.")

    price = await fetch_riftbound_price_for_card(
        riftbound_id=normalized_id,
        tcgplayer_id=tcgplayer_id,
        name=name,
        set_id=set_id,
    )
    return {"price": price}


@router.get("/riftbound/price/{tcgplayer_id}")
async def get_riftbound_price(
    tcgplayer_id: str,
    name: str | None = Query(default=None),
    set_id: str | None = Query(default=None),
) -> dict[str, dict[str, object] | None]:
    price = await fetch_riftbound_price_for_card(
        tcgplayer_id=tcgplayer_id,
        name=name,
        set_id=set_id,
    )
    return {"price": price}
