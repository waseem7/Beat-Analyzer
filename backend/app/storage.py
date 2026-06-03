from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from .models import Track, TrackStatus

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = Path("/data") if Path("/data").exists() else BASE_DIR.parent / "data"
MUSIC_DIR = DATA_DIR / "music"
ANALYSIS_DIR = DATA_DIR / "analysis"
EXPORT_DIR = DATA_DIR / "exports"

for directory in (MUSIC_DIR, ANALYSIS_DIR, EXPORT_DIR):
    directory.mkdir(parents=True, exist_ok=True)


def track_path(track_id: str) -> Path:
    return ANALYSIS_DIR / f"{track_id}.json"


def save_track(track: Track) -> Track:
    track.updated_at = datetime.now(timezone.utc)
    track_path(track.id).write_text(track.model_dump_json(indent=2), encoding="utf-8")
    return track


def load_track(track_id: str) -> Track:
    path = track_path(track_id)
    if not path.exists():
        raise KeyError(track_id)
    return Track.model_validate_json(path.read_text(encoding="utf-8"))


def list_tracks() -> list[Track]:
    tracks: list[Track] = []
    for path in sorted(ANALYSIS_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            tracks.append(Track.model_validate_json(path.read_text(encoding="utf-8")))
        except (json.JSONDecodeError, ValueError):
            continue
    return tracks


def music_path(track: Track) -> Path:
    return MUSIC_DIR / track.stored_filename


def set_failed(track: Track, error: str) -> Track:
    track.status = TrackStatus.failed
    track.error = error
    return save_track(track)
