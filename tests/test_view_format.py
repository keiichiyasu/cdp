from src.core.events import AppState, ViewState
from src.ui.view import format_artist_line, format_track_line


def test_track_line_with_title():
    vs = ViewState(AppState.PLAYING, track_number=3,
                   track_title="Blue in Green")
    assert format_track_line(vs) == "3. Blue in Green"


def test_track_line_without_metadata():
    vs = ViewState(AppState.PLAYING, track_number=3)
    assert format_track_line(vs) == "3. トラック 3"


def test_track_line_finished():
    vs = ViewState(AppState.FINISHED, track_number=3)
    assert format_track_line(vs) == "再生終了"


def test_artist_line_full():
    vs = ViewState(AppState.PLAYING, track_number=2, track_total=9,
                   artist="Miles Davis", album_title="Kind of Blue")
    assert format_artist_line(vs) == "Miles Davis — Kind of Blue   2 / 9"


def test_artist_line_counter_only():
    vs = ViewState(AppState.PLAYING, track_number=2, track_total=9)
    assert format_artist_line(vs) == "2 / 9"
