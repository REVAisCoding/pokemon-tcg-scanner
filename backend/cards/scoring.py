from models import ExtractedCardInfo, ScannedCardResponse
from cards.mappers import get_search_names
from utils.text import normalize_card_number


def score_candidate(card: ScannedCardResponse, extracted: ExtractedCardInfo) -> int:
    score = 0
    card_name = card.name.lower()

    for name in get_search_names(extracted):
        normalized = name.lower()
        if normalized == card_name:
            score += 100
        elif normalized in card_name or card_name in normalized:
            score += 50

    extracted_number = normalize_card_number(extracted.number)
    candidate_number = normalize_card_number(card.number)
    if extracted_number and candidate_number and extracted_number == candidate_number:
        score += 1000

    set_name = (extracted.set or "").strip().lower()
    if set_name and set_name in card.setName.lower():
        score += 500

    language = (extracted.language or "").lower()
    if any(token in language for token in ("portug", "brasil", "brazil")) and card.id.startswith(
        "tcgdex-"
    ):
        score += 200

    return score


def rank_candidates(
    candidates: list[ScannedCardResponse],
    extracted: ExtractedCardInfo,
) -> list[ScannedCardResponse]:
    return sorted(
        candidates,
        key=lambda card: score_candidate(card, extracted),
        reverse=True,
    )
