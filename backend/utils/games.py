from models import GameType


def normalize_game_type(value: str | None) -> GameType:
    normalized = (value or "pokemon").strip().lower()
    if normalized in {"riftbound", "runeterra"}:
        return "riftbound"
    if normalized == "magic":
        return "magic"
    if normalized in {"onepiece", "one-piece", "one_piece"}:
        return "onepiece"
    return "pokemon"
