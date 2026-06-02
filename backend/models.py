from typing import Literal

from pydantic import BaseModel

GameType = Literal["pokemon", "riftbound", "magic", "onepiece"]
ConfidenceLevel = Literal["high", "medium", "low"]


class ExtractedCardInfo(BaseModel):
    name: str | None = None
    nameEnglish: str | None = None
    number: str | None = None
    set: str | None = None
    language: str | None = None


class ScannedCardResponse(BaseModel):
    id: str
    name: str
    setName: str
    number: str
    type: str
    imageUrl: str
    accentColor: str
    rarity: str | None = None
    estimatedValueBrl: float | None = None


class ScanCardResponse(BaseModel):
    confidence: ConfidenceLevel
    extracted: ExtractedCardInfo
    candidates: list[ScannedCardResponse]
