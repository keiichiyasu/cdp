from src.core.events import AppState, TrackRef, ViewState


def test_view_state_defaults():
    vs = ViewState(state=AppState.NO_DISC)
    assert vs.track_number is None
    assert vs.error_message is None


def test_track_ref_duration_optional():
    assert TrackRef(number=1).duration is None
    assert TrackRef(number=2, duration=180.0).duration == 180.0
