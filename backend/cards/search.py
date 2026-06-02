import httpx

import config
from cards.mappers import resolve_tcgdex_lang
from cards.pokemon_tcg import search_pokemontcg_candidates
from cards.scoring import rank_candidates
from cards.tcgdex import check_tcgdex_available, search_tcgdex_candidates
from models import ExtractedCardInfo, ScannedCardResponse

TCG_API_TIMEOUT = httpx.Timeout(10.0, read=25.0)


async def search_candidates(extracted: ExtractedCardInfo) -> list[ScannedCardResponse]:
    pool: list[ScannedCardResponse] = []
    seen_ids: set[str] = set()
    lang = resolve_tcgdex_lang(extracted.language)

    headers: dict[str, str] = {}
    if config.POKEMON_TCG_API_KEY:
        headers["X-Api-Key"] = config.POKEMON_TCG_API_KEY

    async with httpx.AsyncClient(timeout=TCG_API_TIMEOUT, headers=headers) as client:
        for card in await search_pokemontcg_candidates(client, extracted):
            if card.id in seen_ids:
                continue
            seen_ids.add(card.id)
            pool.append(card)

        if await check_tcgdex_available(client):
            for card in await search_tcgdex_candidates(client, extracted, lang):
                if card.id in seen_ids:
                    continue
                seen_ids.add(card.id)
                pool.append(card)

    return rank_candidates(pool, extracted)[: config.MAX_CANDIDATES]
