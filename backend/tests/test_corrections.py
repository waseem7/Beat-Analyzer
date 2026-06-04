from backend.app.models import AnalysisResult, BeatMarker, CorrectionRequest, Track
from backend.app.services.corrections import apply_correction


def make_track() -> Track:
    beat_times = [float(i) for i in range(16)]
    beats = [BeatMarker(index=i + 1, time=float(i), count8=(i % 8) + 1) for i in range(16)]
    analysis = AnalysisResult(
        bpm=120,
        bpm_display_half=60,
        beat_times=beat_times,
        downbeat_times=[0, 4, 8, 12],
        candidate_salsa_1=0,
        candidate_salsa_5=4,
        beats=beats,
    )
    return Track(filename="test.mp3", stored_filename="test.mp3", raw_analysis=analysis, corrected_analysis=analysis.model_copy(deep=True))


def test_set_five_recounts_candidate_one_four_beats_earlier():
    track = apply_correction(make_track(), CorrectionRequest(action="set_five", time=8.1))
    assert track.corrected_analysis.candidate_salsa_1 == 4.0
    assert track.corrected_analysis.candidate_salsa_5 == 8.0
    assert track.correction.review_status == "reviewed"


def test_swap_one_five_moves_one_to_old_five():
    track = apply_correction(make_track(), CorrectionRequest(action="swap_one_five"))
    assert track.corrected_analysis.candidate_salsa_1 == 4.0
    assert track.corrected_analysis.candidate_salsa_5 == 8.0


def test_set_bpm_creates_manual_grid_when_analysis_has_no_beats():
    analysis = AnalysisResult(duration=10, analyzer="duration-only-fallback")
    track = Track(filename="test.mp3", stored_filename="test.mp3", raw_analysis=analysis, corrected_analysis=analysis.model_copy(deep=True))

    corrected = apply_correction(track, CorrectionRequest(action="set_bpm", bpm=120, time=1.0))

    assert corrected.corrected_analysis.bpm == 120
    assert len(corrected.corrected_analysis.beat_times) >= 18
    assert corrected.corrected_analysis.candidate_salsa_1 == 1.0
