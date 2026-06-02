from models import GameType


def normalize_game_type(value: str | None) -> GameType:
    normalized = (value or "pokemon").strip().lower()
    if normalized in {"riftbound", "runeterra"}:
        return "riftbound"
    if normalized == "magic":
        return "magic"
    return "pokemon"
