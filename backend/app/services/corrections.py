from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone

from ..models import AnalysisResult, CorrectionRequest, Track


def _nearest_beat_index(analysis: AnalysisResult, time: float) -> int | None:
    if not analysis.beat_times:
        return None
    return min(range(len(analysis.beat_times)), key=lambda idx: abs(analysis.beat_times[idx] - time))


def _recount_from_index(analysis: AnalysisResult, first_index: int) -> AnalysisResult:
    for idx, marker in enumerate(analysis.beats):
        count8 = ((idx - first_index) % 8) + 1
        marker.count8 = count8
        marker.is_downbeat = count8 in (1, 5)
        marker.is_salsa_1 = count8 == 1
        marker.is_salsa_5 = count8 == 5

    analysis.downbeat_times = [m.time for m in analysis.beats if m.is_downbeat]

    anchor_index = max(first_index, 0)

    one_marker = next(
        (m for idx, m in enumerate(analysis.beats) if idx >= anchor_index and m.is_salsa_1),
        None,
    )
    if one_marker is None:
        one_marker = next((m for m in analysis.beats if m.is_salsa_1), None)

    five_marker = None
    if one_marker is not None:
        five_marker = next(
            (m for m in analysis.beats if m.is_salsa_5 and m.time >= one_marker.time),
            None,
        )

    if five_marker is None:
        five_marker = next((m for m in analysis.beats if m.is_salsa_5), None)

    analysis.candidate_salsa_1 = one_marker.time if one_marker else None
    analysis.candidate_salsa_5 = five_marker.time if five_marker else None

    return analysis
    for idx, marker in enumerate(analysis.beats):
        count8 = ((idx - first_index) % 8) + 1
        marker.count8 = count8
        marker.is_downbeat = count8 in (1, 5)
        marker.is_salsa_1 = count8 == 1
        marker.is_salsa_5 = count8 == 5
    analysis.downbeat_times = [m.time for m in analysis.beats if m.is_downbeat]
    one = next((m.time for m in analysis.beats if m.is_salsa_1), None)
    five = next((m.time for m in analysis.beats if m.is_salsa_5), None)
    analysis.candidate_salsa_1 = one
    analysis.candidate_salsa_5 = five
    return analysis


def apply_correction(track: Track, request: CorrectionRequest) -> Track:
    if not track.corrected_analysis and track.raw_analysis:
        track.corrected_analysis = deepcopy(track.raw_analysis)
    if not track.corrected_analysis:
        raise ValueError("track has no analysis to correct")

    analysis = track.corrected_analysis
    action = request.action
    event = {"action": action, "time": request.time, "bpm": request.bpm, "at": datetime.now(timezone.utc).isoformat()}

    if action in {"set_one", "set_five"}:
        if request.time is None:
            raise ValueError("time is required")
        idx = _nearest_beat_index(analysis, request.time)
        if idx is None:
            raise ValueError("analysis has no beats")
        first_index = idx if action == "set_one" else idx - 4
        _recount_from_index(analysis, first_index)
        track.correction.first_salsa_1 = analysis.candidate_salsa_1
        track.correction.first_salsa_5 = analysis.candidate_salsa_5
        track.correction.review_status = "reviewed"
    elif action == "swap_one_five":
        first_time = analysis.candidate_salsa_5
        if first_time is None:
            raise ValueError("no salsa 5 candidate is available")
        idx = _nearest_beat_index(analysis, first_time)
        if idx is not None:
            _recount_from_index(analysis, idx)
        track.correction.first_salsa_1 = analysis.candidate_salsa_1
        track.correction.first_salsa_5 = analysis.candidate_salsa_5
        track.correction.review_status = "reviewed"
    elif action in {"shift_plus_beat", "shift_minus_beat", "shift_plus_phrase", "shift_minus_phrase"}:
        delta = {"shift_plus_beat": 1, "shift_minus_beat": -1, "shift_plus_phrase": 4, "shift_minus_phrase": -4}[action]
        current = _nearest_beat_index(analysis, analysis.candidate_salsa_1 or 0) or 0
        _recount_from_index(analysis, current + delta)
    elif action in {"double_bpm", "half_bpm", "set_bpm"}:
        if action == "double_bpm" and analysis.bpm:
            analysis.bpm *= 2
        elif action == "half_bpm" and analysis.bpm:
            analysis.bpm /= 2
        elif action == "set_bpm" and request.bpm:
            analysis.bpm = request.bpm
        analysis.bpm = round(float(analysis.bpm or 0), 2)
        analysis.bpm_display_half = round(analysis.bpm / 2, 2)
        track.correction.bpm = analysis.bpm
    elif action == "mark_reviewed":
        track.correction.review_status = "reviewed"
    else:
        raise ValueError(f"unknown correction action: {action}")

    if request.notes is not None:
        track.correction.notes = request.notes
    track.correction.history.append(event)
    return track
