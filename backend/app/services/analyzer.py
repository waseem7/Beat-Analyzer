from __future__ import annotations

import math
from pathlib import Path

from ..models import AnalysisResult, BeatMarker, Confidence


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _round_times(values: list[float]) -> list[float]:
    return [round(v, 3) for v in values if math.isfinite(v) and v >= 0]


def _build_markers(beat_times: list[float], first_one: float | None, beat_confidence: float) -> list[BeatMarker]:
    markers: list[BeatMarker] = []
    if not beat_times:
        return markers
    first_index = 0
    if first_one is not None:
        first_index = min(range(len(beat_times)), key=lambda idx: abs(beat_times[idx] - first_one))
    for idx, beat_time in enumerate(beat_times):
        offset = idx - first_index
        count8 = (offset % 8) + 1
        markers.append(
            BeatMarker(
                index=idx + 1,
                time=round(beat_time, 3),
                count8=count8,
                is_downbeat=count8 in (1, 5),
                is_salsa_1=count8 == 1,
                is_salsa_5=count8 == 5,
                confidence=round(beat_confidence, 3),
            )
        )
    return markers


def _fixed_grid_from_bpm(duration: float, bpm: float, start: float = 0.0) -> list[float]:
    if bpm <= 0 or duration <= 0:
        return []
    interval = 60.0 / bpm
    count = int(max(0, math.floor((duration - start) / interval))) + 1
    return _round_times([start + i * interval for i in range(count)])


def _estimate_with_librosa(audio_path: Path) -> AnalysisResult:
    import librosa  # intentionally optional in local dev; installed in Docker image
    import numpy as np

    y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))
    tempo_raw, beat_frames = librosa.beat.beat_track(y=y, sr=sr, units="frames", trim=False)
    tempo = float(np.asarray(tempo_raw).reshape(-1)[0])
    if tempo and tempo < 120:
        working_bpm = tempo * 2.0
    else:
        working_bpm = tempo

    beat_times = librosa.frames_to_time(beat_frames, sr=sr).astype(float).tolist()
    if len(beat_times) < 8 and working_bpm:
        beat_times = _fixed_grid_from_bpm(duration, working_bpm, beat_times[0] if beat_times else 0.0)
    beat_times = _round_times(beat_times)

    intervals = np.diff(beat_times) if len(beat_times) > 1 else np.array([])
    median_interval = float(np.median(intervals)) if intervals.size else (60.0 / working_bpm if working_bpm else 0.0)
    interval_jitter = float(np.std(intervals) / median_interval) if median_interval and intervals.size else 1.0
    grid_conf = _clamp(1.0 - interval_jitter * 2.5)

    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    tempo_candidates = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, aggregate=None)
    tempo_std = float(np.std(tempo_candidates)) if len(tempo_candidates) else 999.0
    bpm_conf = _clamp(1.0 - min(tempo_std, 40.0) / 40.0)

    first_one = beat_times[0] if beat_times else None
    downbeats = beat_times[0::4]
    first_five = beat_times[4] if len(beat_times) > 4 else None
    downbeat_conf = _clamp(grid_conf * 0.82)
    salsa_conf = _clamp(downbeat_conf * 0.72)
    overall = _clamp((bpm_conf + grid_conf + downbeat_conf + salsa_conf) / 4.0)

    warnings: list[str] = []
    if salsa_conf < 0.7:
        warnings.append("possible 1/5 ambiguity; manual review recommended")
    if tempo and tempo < 120:
        warnings.append("display BPM doubled for dance-count grid; half-time BPM is available")
    if beat_times and beat_times[0] > 3:
        warnings.append("intro before first stable beat may need review")

    confidence = Confidence(
        bpm=round(bpm_conf, 3),
        grid=round(grid_conf, 3),
        downbeat=round(downbeat_conf, 3),
        salsa_one=round(salsa_conf, 3),
        overall=round(overall, 3),
    )
    return AnalysisResult(
        bpm=round(working_bpm, 2) if working_bpm else None,
        bpm_display_half=round(working_bpm / 2.0, 2) if working_bpm else None,
        duration=round(duration, 3),
        beat_times=beat_times,
        downbeat_times=_round_times(downbeats),
        candidate_salsa_1=first_one,
        candidate_salsa_5=first_five,
        confidence=confidence,
        warnings=warnings,
        beats=_build_markers(beat_times, first_one, grid_conf),
        analyzer="librosa",
    )


def _estimate_with_ffprobe(audio_path: Path) -> float | None:
    import json
    import subprocess

    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(audio_path)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return None
    payload = json.loads(result.stdout or "{}")
    duration = payload.get("format", {}).get("duration")
    return round(float(duration), 3) if duration else None


def _fallback_analysis(audio_path: Path) -> AnalysisResult:
    duration = _estimate_with_ffprobe(audio_path) or 0.0
    bpm = 180.0
    beat_times = _fixed_grid_from_bpm(duration, bpm)
    first_one = beat_times[0] if beat_times else None
    confidence = Confidence(bpm=0.25, grid=0.2, downbeat=0.15, salsa_one=0.1, overall=0.175)
    warnings = [
        "librosa analysis unavailable; generated a low-confidence placeholder grid",
        "install Docker dependencies or review this track manually",
        "possible 1/5 ambiguity; manual review required",
    ]
    return AnalysisResult(
        bpm=bpm,
        bpm_display_half=90.0,
        duration=duration,
        beat_times=beat_times,
        downbeat_times=beat_times[0::4],
        candidate_salsa_1=first_one,
        candidate_salsa_5=beat_times[4] if len(beat_times) > 4 else None,
        confidence=confidence,
        warnings=warnings,
        beats=_build_markers(beat_times, first_one, confidence.grid),
        analyzer="fallback",
    )


def analyze_audio(audio_path: Path) -> AnalysisResult:
    try:
        return _estimate_with_librosa(audio_path)
    except Exception as exc:  # analysis must fail soft so manual grid can still be created
        result = _fallback_analysis(audio_path)
        result.warnings.insert(0, f"automatic analyzer failed: {exc.__class__.__name__}")
        return result
