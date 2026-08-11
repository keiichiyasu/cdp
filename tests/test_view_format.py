from src.core.events import AppState, ViewState
from src.ui.view import (ensure_fullscreen, format_artist_line,
                         format_track_line)


class StubRoot:
    """attributes("-fullscreen") の読み書きだけを持つ最小の偽 root。"""

    def __init__(self, applied):
        self.applied = applied
        self.requests = []

    def attributes(self, name, value=None):
        assert name == "-fullscreen"
        if value is None:
            return self.applied
        self.requests.append(value)
        self.applied = 1 if value else 0


def test_ensure_fullscreen_reapplies_when_request_did_not_take():
    """labwc + XWayland では全画面要求が通らないことがある。

    通らないまま放置すると、View は place() だけで組んでいるため
    ウィンドウが最小サイズ(200x200)に潰れる。要求し直す。
    """
    root = StubRoot(applied=0)
    assert ensure_fullscreen(root) is False
    assert root.requests == [True]


def test_ensure_fullscreen_leaves_applied_window_alone():
    root = StubRoot(applied=1)
    assert ensure_fullscreen(root) is True
    assert root.requests == []


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
