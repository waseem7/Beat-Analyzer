from __future__ import annotations

import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import BackgroundTasks, FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, PlainTextResponse, Response
from fastapi.staticfiles import StaticFiles

from .models import CorrectionRequest, Track, TrackStatus, TrackSummary
from .services.analyzer import analyze_audio
from .services.corrections import apply_correction
from .services.exports import beat_detail_csv, master_json, persist_export, track_summary_csv, write_mp3_tags
from .storage import MUSIC_DIR, load_track, list_tracks, music_path, save_track, set_failed

app = FastAPI(title="Latin Beat Analyzer", version="0.1.0")
STATIC_DIR = Path(__file__).parent / "static"


def _summary(track: Track) -> TrackSummary:
    analysis = track.corrected_analysis or track.raw_analysis
    return TrackSummary(
        id=track.id,
        filename=track.filename,
        status=track.status,
        bpm=analysis.bpm if analysis else None,
        candidate_salsa_1=analysis.candidate_salsa_1 if analysis else None,
        candidate_salsa_5=analysis.candidate_salsa_5 if analysis else None,
        confidence=analysis.confidence if analysis else None,
        review_status=track.correction.review_status,
        warnings=analysis.warnings if analysis else [],
    )


def _run_analysis(track_id: str) -> None:
    track = load_track(track_id)
    try:
        track.status = TrackStatus.analyzing
        save_track(track)
        track.raw_analysis = analyze_audio(music_path(track))
        track.corrected_analysis = track.raw_analysis.model_copy(deep=True)
        track.status = TrackStatus.analyzed
        save_track(track)
    except Exception as exc:
        set_failed(track, str(exc))


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/tracks", response_model=TrackSummary)
async def upload_track(background_tasks: BackgroundTasks, file: UploadFile = File(...)) -> TrackSummary:
    if not file.filename:
        raise HTTPException(400, "filename is required")
    suffix = Path(file.filename).suffix.lower()
    if suffix not in {".mp3", ".wav", ".flac", ".m4a", ".aac", ".ogg"}:
        raise HTTPException(400, "upload an audio file: mp3, wav, flac, m4a, aac, or ogg")
    track_id = uuid4().hex
    stored_filename = f"{track_id}{suffix}"
    destination = MUSIC_DIR / stored_filename
    with destination.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)
    track = Track(id=track_id, filename=file.filename, stored_filename=stored_filename, content_type=file.content_type)
    save_track(track)
    background_tasks.add_task(_run_analysis, track.id)
    return _summary(track)


@app.post("/api/tracks/{track_id}/analyze", response_model=TrackSummary)
def analyze_track(track_id: str, background_tasks: BackgroundTasks) -> TrackSummary:
    track = _get_track(track_id)
    background_tasks.add_task(_run_analysis, track.id)
    track.status = TrackStatus.analyzing
    save_track(track)
    return _summary(track)


@app.get("/api/tracks", response_model=list[TrackSummary])
def tracks() -> list[TrackSummary]:
    return [_summary(track) for track in list_tracks()]


def _get_track(track_id: str) -> Track:
    try:
        return load_track(track_id)
    except KeyError as exc:
        raise HTTPException(404, "track not found") from exc


@app.get("/api/tracks/{track_id}", response_model=Track)
def get_track(track_id: str) -> Track:
    return _get_track(track_id)


@app.get("/api/tracks/{track_id}/audio")
def audio(track_id: str) -> FileResponse:
    track = _get_track(track_id)
    return FileResponse(music_path(track), filename=track.filename, media_type=track.content_type or "audio/mpeg")


@app.post("/api/tracks/{track_id}/corrections", response_model=Track)
def correct_track(track_id: str, request: CorrectionRequest) -> Track:
    track = _get_track(track_id)
    try:
        track = apply_correction(track, request)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return save_track(track)


@app.post("/api/tracks/{track_id}/write-tags", response_model=TrackSummary)
def write_tags(track_id: str) -> TrackSummary:
    track = _get_track(track_id)
    try:
        write_mp3_tags(track)
    except Exception as exc:
        raise HTTPException(400, str(exc)) from exc
    return _summary(track)


@app.get("/api/exports/tracks.csv")
def export_tracks_csv() -> Response:
    content = track_summary_csv(list_tracks())
    persist_export("tracks.csv", content)
    return PlainTextResponse(content, media_type="text/csv")


@app.get("/api/tracks/{track_id}/exports/beats.csv")
def export_beats_csv(track_id: str) -> Response:
    track = _get_track(track_id)
    content = beat_detail_csv(track)
    persist_export(f"{track.id}-beats.csv", content)
    return PlainTextResponse(content, media_type="text/csv")


@app.get("/api/tracks/{track_id}/exports/analysis.json")
def export_analysis_json(track_id: str) -> Response:
    track = _get_track(track_id)
    content = master_json(track)
    persist_export(f"{track.id}-analysis.json", content)
    return Response(content, media_type="application/json")


app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
