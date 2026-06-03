from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from .models import Track, TrackStatus

DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
IMPORT_DIR = Path(os.getenv("IMPORT_DIR", "/import"))
MUSIC_DIR = DATA_DIR / "music"
ANALYSIS_DIR = DATA_DIR / "analysis"
EXPORT_DIR = DATA_DIR / "exports"
SUPPORTED_AUDIO_EXTENSIONS = {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}

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
    if track.source_path:
        return Path(track.source_path)
    return MUSIC_DIR / track.stored_filename


def existing_source_paths() -> set[str]:
    return {track.source_path for track in list_tracks() if track.source_path}


def scan_import_files() -> tuple[list[Path], int]:
    if not IMPORT_DIR.exists():
        return [], 0
    files: list[Path] = []
    skipped_unsupported = 0
    for path in sorted(IMPORT_DIR.rglob("*")):
        if not path.is_file():
            continue
        if path.suffix.lower() not in SUPPORTED_AUDIO_EXTENSIONS:
            skipped_unsupported += 1
            continue
        files.append(path)
    return files, skipped_unsupported


def set_failed(track: Track, error: str) -> Track:
    track.status = TrackStatus.failed
    track.error = error
    return save_track(track)
