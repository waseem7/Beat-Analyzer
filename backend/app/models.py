from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class TrackStatus(str, Enum):
    uploaded = "uploaded"
    analyzing = "analyzing"
    analyzed = "analyzed"
    failed = "failed"


class Confidence(BaseModel):
    bpm: float = 0.0
    grid: float = 0.0
    downbeat: float = 0.0
    salsa_one: float = 0.0
    overall: float = 0.0


class BeatMarker(BaseModel):
    index: int
    time: float
    count8: int
    is_downbeat: bool = False
    is_salsa_1: bool = False
    is_salsa_5: bool = False
    confidence: float = 0.0


class AnalysisResult(BaseModel):
    bpm: float | None = None
    bpm_display_half: float | None = None
    duration: float | None = None
    beat_times: list[float] = Field(default_factory=list)
    downbeat_times: list[float] = Field(default_factory=list)
    candidate_salsa_1: float | None = None
    candidate_salsa_5: float | None = None
    phrase_length_beats: int = 8
    confidence: Confidence = Field(default_factory=Confidence)
    warnings: list[str] = Field(default_factory=list)
    beats: list[BeatMarker] = Field(default_factory=list)
    analyzer: str = "pending"


class Correction(BaseModel):
    first_salsa_1: float | None = None
    first_salsa_5: float | None = None
    bpm: float | None = None
    review_status: str = "needs_review"
    notes: str = ""
    history: list[dict[str, Any]] = Field(default_factory=list)


class Track(BaseModel):
    id: str = Field(default_factory=lambda: uuid4().hex)
    filename: str
    stored_filename: str
    content_type: str | None = None
    source_path: str | None = None
    imported: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    status: TrackStatus = TrackStatus.uploaded
    error: str | None = None
    raw_analysis: AnalysisResult | None = None
    corrected_analysis: AnalysisResult | None = None
    correction: Correction = Field(default_factory=Correction)


class CorrectionRequest(BaseModel):
    action: str
    time: float | None = None
    bpm: float | None = None
    notes: str | None = None


class TrackSummary(BaseModel):
    id: str
    filename: str
    status: TrackStatus
    imported: bool = False
    bpm: float | None = None
    candidate_salsa_1: float | None = None
    candidate_salsa_5: float | None = None
    confidence: Confidence | None = None
    review_status: str
    warnings: list[str] = Field(default_factory=list)


class ImportScanResponse(BaseModel):
    imported: list[TrackSummary] = Field(default_factory=list)
    skipped_existing: int = 0
    skipped_unsupported: int = 0


class SettingsResponse(BaseModel):
    data_dir: str
    music_dir: str
    analysis_dir: str
    export_dir: str
    import_dir: str
    auth_enabled: bool = False
    supported_audio_extensions: list[str]
