from __future__ import annotations

import math
from pathlib import Path
from typing import Any

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


def _first_onset_time(librosa: Any, onset_env: Any, sr: int) -> float:
    onset_frames = librosa.onset.onset_detect(onset_envelope=onset_env, sr=sr, backtrack=True)
    onset_times = librosa.frames_to_time(onset_frames, sr=sr).astype(float).tolist()
    return round(float(onset_times[0]), 3) if onset_times else 0.0


def _normalize_dance_bpm(tempo: float) -> float:
    bpm = float(tempo or 0.0)
    while bpm and bpm < 115.0:
        bpm *= 2.0
    while bpm > 230.0:
        bpm /= 2.0
    return bpm


def _score_grid(beat_times: list[float], onset_env: Any, librosa: Any, sr: int, duration: float) -> tuple[float, float]:
    import numpy as np

    if len(beat_times) < 8:
        return 0.0, 1.0
    intervals = np.diff(beat_times)
    median_interval = float(np.median(intervals)) if intervals.size else 0.0
    jitter = float(np.std(intervals) / median_interval) if median_interval else 1.0
    beat_frames = librosa.time_to_frames(beat_times, sr=sr)
    onset_values = onset_env[np.clip(beat_frames, 0, len(onset_env) - 1)] if len(onset_env) else np.array([])
    onset_score = float(np.mean(onset_values) / (np.percentile(onset_env, 95) or 1.0)) if len(onset_values) and len(onset_env) else 0.0
    coverage = min(1.0, (beat_times[-1] - beat_times[0]) / max(duration, 1.0))
    confidence = _clamp((1.0 - jitter * 2.2) * 0.55 + onset_score * 0.25 + coverage * 0.2)
    return confidence, jitter


def _candidate_grids(librosa: Any, y: Any, sr: int, onset_env: Any, duration: float) -> list[tuple[str, float, list[float], float, float]]:
    import numpy as np

    candidates: list[tuple[str, float, list[float], float, float]] = []
    tempo_values = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, aggregate=None)
    tempo_seeds = [float(np.median(tempo_values))] if len(tempo_values) else []
    tempo_seeds.extend([70.0, 85.0, 95.0, 110.0, 125.0, 145.0, 165.0, 185.0])

    for seed in dict.fromkeys(round(seed, 1) for seed in tempo_seeds if seed and math.isfinite(seed)):
        try:
            tempo_raw, beat_frames = librosa.beat.beat_track(
                y=y,
                sr=sr,
                onset_envelope=onset_env,
                start_bpm=seed,
                units="frames",
                trim=False,
                tightness=80,
            )
        except RuntimeError:
            continue
        tempo = float(np.asarray(tempo_raw).reshape(-1)[0])
        beat_times = _round_times(librosa.frames_to_time(beat_frames, sr=sr).astype(float).tolist())
        score, jitter = _score_grid(beat_times, onset_env, librosa, sr, duration)
        candidates.append(("librosa-beat-track", _normalize_dance_bpm(tempo), beat_times, score, jitter))

    try:
        pulse = librosa.beat.plp(onset_envelope=onset_env, sr=sr)
        pulse_frames = librosa.util.localmax(pulse)
        pulse_times = _round_times(librosa.frames_to_time(pulse_frames.nonzero()[0], sr=sr).astype(float).tolist())
        if len(pulse_times) >= 8:
            intervals = np.diff(pulse_times)
            tempo = 60.0 / float(np.median(intervals)) if len(intervals) else 0.0
            score, jitter = _score_grid(pulse_times, onset_env, librosa, sr, duration)
            candidates.append(("librosa-plp", _normalize_dance_bpm(tempo), pulse_times, score * 0.9, jitter))
    except RuntimeError:
        pass

    return candidates


def _estimate_with_librosa(audio_path: Path) -> AnalysisResult:
    import librosa  # intentionally optional in local dev; installed in Docker image
    import numpy as np

    warnings: list[str] = []
    y, sr = librosa.load(str(audio_path), sr=22050, mono=True)
    duration = float(librosa.get_duration(y=y, sr=sr))
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    candidates = _candidate_grids(librosa, y, sr, onset_env, duration)
    candidates = [candidate for candidate in candidates if candidate[1] and len(candidate[2]) >= 8]

    if candidates:
        analyzer, working_bpm, beat_times, grid_conf, jitter = max(candidates, key=lambda item: item[3])
    else:
        tempo_values = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, aggregate=None)
        tempo = float(np.median(tempo_values)) if len(tempo_values) else 0.0
        working_bpm = _normalize_dance_bpm(tempo)
        start = _first_onset_time(librosa, onset_env, sr)
        beat_times = _fixed_grid_from_bpm(duration, working_bpm, start) if working_bpm else []
        analyzer = "librosa-tempo-grid"
        grid_conf = 0.38 if beat_times else 0.0
        jitter = 0.45
        warnings.append("beat tracker could not lock reliably; built a tempo-derived grid from onset analysis")

    beat_times = _round_times(beat_times)
    tempo_candidates = librosa.feature.tempo(onset_envelope=onset_env, sr=sr, aggregate=None)
    normalized_tempos = [_normalize_dance_bpm(float(value)) for value in tempo_candidates if value and math.isfinite(float(value))]
    tempo_std = float(np.std(normalized_tempos)) if normalized_tempos else 999.0
    bpm_conf = _clamp(1.0 - min(tempo_std, 45.0) / 45.0)
    if grid_conf < 0.45:
        bpm_conf = min(bpm_conf, 0.55)

    first_one = beat_times[0] if beat_times else None
    downbeats = beat_times[0::4]
    first_five = beat_times[4] if len(beat_times) > 4 else None
    downbeat_conf = _clamp(grid_conf * 0.82)
    salsa_conf = _clamp(downbeat_conf * 0.72)
    overall = _clamp((bpm_conf + grid_conf + downbeat_conf + salsa_conf) / 4.0)

    if not beat_times:
        warnings.append("automatic analyzer could not create a beatgrid; tap/set BPM manually or try a cleaner source file")
    elif grid_conf < 0.55:
        warnings.append("low-confidence automatic grid; verify against playback before exporting")
    if salsa_conf < 0.7:
        warnings.append("possible 1/5 ambiguity; manual review recommended")
    if working_bpm and working_bpm >= 150:
        warnings.append("dance-count BPM is high; compare with half-time display before tagging")
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
        analyzer=analyzer,
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
    confidence = Confidence(bpm=0.0, grid=0.0, downbeat=0.0, salsa_one=0.0, overall=0.0)
    warnings = [
        "automatic audio analysis failed before a trustworthy BPM could be estimated",
        "no fake default BPM was written; use Re-analyze after fixing Docker dependencies or set BPM manually",
    ]
    return AnalysisResult(
        bpm=None,
        bpm_display_half=None,
        duration=duration,
        beat_times=[],
        downbeat_times=[],
        candidate_salsa_1=None,
        candidate_salsa_5=None,
        confidence=confidence,
        warnings=warnings,
        beats=[],
        analyzer="duration-only-fallback",
    )


def analyze_audio(audio_path: Path) -> AnalysisResult:
    try:
        return _estimate_with_librosa(audio_path)
    except Exception as exc:  # analysis must fail soft so manual review can still open the file
        result = _fallback_analysis(audio_path)
        result.warnings.insert(0, f"automatic analyzer failed: {exc.__class__.__name__}: {exc}")
        return result
