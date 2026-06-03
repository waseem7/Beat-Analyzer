from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path

from ..models import Track
from ..storage import EXPORT_DIR, music_path


def active_analysis(track: Track):
    return track.corrected_analysis or track.raw_analysis


def track_summary_csv(tracks: list[Track]) -> str:
    buf = StringIO()
    fieldnames = [
        "file",
        "bpm",
        "bpm_half",
        "first_salsa_1",
        "first_salsa_5",
        "confidence_bpm",
        "confidence_grid",
        "confidence_one",
        "review_needed",
        "warnings",
    ]
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for track in tracks:
        analysis = active_analysis(track)
        conf = analysis.confidence if analysis else None
        writer.writerow(
            {
                "file": track.filename,
                "bpm": analysis.bpm if analysis else "",
                "bpm_half": analysis.bpm_display_half if analysis else "",
                "first_salsa_1": analysis.candidate_salsa_1 if analysis else "",
                "first_salsa_5": analysis.candidate_salsa_5 if analysis else "",
                "confidence_bpm": conf.bpm if conf else "",
                "confidence_grid": conf.grid if conf else "",
                "confidence_one": conf.salsa_one if conf else "",
                "review_needed": track.correction.review_status != "reviewed",
                "warnings": "; ".join(analysis.warnings) if analysis else "",
            }
        )
    return buf.getvalue()


def beat_detail_csv(track: Track) -> str:
    analysis = active_analysis(track)
    buf = StringIO()
    writer = csv.DictWriter(
        buf,
        fieldnames=["file", "beat_index", "time_seconds", "count8", "is_downbeat", "is_salsa_1", "is_salsa_5", "confidence"],
    )
    writer.writeheader()
    if analysis:
        for marker in analysis.beats:
            writer.writerow(
                {
                    "file": track.filename,
                    "beat_index": marker.index,
                    "time_seconds": marker.time,
                    "count8": marker.count8,
                    "is_downbeat": marker.is_downbeat,
                    "is_salsa_1": marker.is_salsa_1,
                    "is_salsa_5": marker.is_salsa_5,
                    "confidence": marker.confidence,
                }
            )
    return buf.getvalue()


def master_json(track: Track) -> str:
    analysis = active_analysis(track)
    payload = {
        "file": track.filename,
        "track_id": track.id,
        "status": track.status,
        "imported": track.imported,
        "source_path": track.source_path,
        "review_status": track.correction.review_status,
        "bpm": analysis.bpm if analysis else None,
        "beatgrid": {
            "type": "fixed",
            "first_salsa_1": analysis.candidate_salsa_1 if analysis else None,
            "first_salsa_5": analysis.candidate_salsa_5 if analysis else None,
            "beats": [marker.model_dump() for marker in analysis.beats] if analysis else [],
        },
        "cues": [
            {"name": "1 - first clean one", "time": analysis.candidate_salsa_1 if analysis else None},
            {"name": "5", "time": analysis.candidate_salsa_5 if analysis else None},
        ],
        "confidence": analysis.confidence.model_dump() if analysis else None,
        "warnings": analysis.warnings if analysis else [],
        "correction": track.correction.model_dump(),
    }
    return json.dumps(payload, indent=2, default=str)


def write_mp3_tags(track: Track) -> None:
    from mutagen.easyid3 import EasyID3
    from mutagen.id3 import ID3, COMM, ID3NoHeaderError

    analysis = active_analysis(track)
    if not analysis or not analysis.bpm:
        raise ValueError("track has no BPM analysis")
    path = music_path(track)
    try:
        tags = EasyID3(str(path))
    except ID3NoHeaderError:
        ID3().save(str(path))
        tags = EasyID3(str(path))
    tags["bpm"] = [str(round(analysis.bpm))]
    tags.save(str(path))
    id3 = ID3(str(path))
    comment = (
        f"Latin Beat Analyzer | 1={analysis.candidate_salsa_1} | 5={analysis.candidate_salsa_5} | "
        f"grid_conf={analysis.confidence.grid:.2f} | one_conf={analysis.confidence.salsa_one:.2f} | "
        f"review={track.correction.review_status}"
    )
    id3.delall("COMM")
    id3.add(COMM(encoding=3, lang="eng", desc="Latin Beat Analyzer", text=comment))
    id3.save(str(path))


def persist_export(filename: str, content: str) -> Path:
    path = EXPORT_DIR / filename
    path.write_text(content, encoding="utf-8")
    return path
