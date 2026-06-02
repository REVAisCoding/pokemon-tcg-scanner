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


ScanJobStatus = Literal["pending", "processing", "completed", "failed"]


class ScanJobCreateResponse(BaseModel):
    jobId: str


class ScanJobResponse(BaseModel):
    id: str
    status: ScanJobStatus
    gameType: GameType
    imageUrl: str | None = None
    detectedName: str | None = None
    resultCandidates: list[ScannedCardResponse] | None = None
    errorMessage: str | None = None
    createdAt: str
    updatedAt: str
