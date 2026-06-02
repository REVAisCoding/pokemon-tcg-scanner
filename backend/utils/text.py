import re

from models import ConfidenceLevel


def clean_text(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text or text.lower() in {"null", "none", "unknown", "n/a"}:
        return None
    return text


def clean_number(value: object) -> str | None:
    text = clean_text(value)
    if not text:
        return None
    match = re.search(r"\d+", text)
    return match.group(0) if match else None


def normalize_confidence(value: str | None) -> ConfidenceLevel:
    normalized = (value or "low").strip().lower()
    if normalized in {"high", "medium", "low"}:
        return normalized  # type: ignore[return-value]
    return "low"


def normalize_card_number(value: str | None) -> str | None:
    if not value:
        return None
    match = re.search(r"\d+", value)
    if not match:
        return None
    return match.group(0).lstrip("0") or "0"


def escape_query_value(value: str) -> str:
    return value.replace('"', '\\"')
