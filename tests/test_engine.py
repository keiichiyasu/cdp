import sys
import time

import pytest

from src.audio.engine import PlaybackEngine, default_stream_factory
from src.audio.sources import CHUNK_BYTES, SourceStallError
from src.core.events import (PlaybackError, PlaybackFinished, TrackChanged,
                             TrackRef, TrackSkipped)
from tests.support import wait_until


def make_chunks(n):
    return [b"\x00" * CHUNK_BYTES for _ in range(n)]


class FakeStream:
    def __init__(self):
        self.written = 0
        self.started = False
        self.closed = False

    def start(self):
        self.started = True

    def write(self, data):
        self.written += len(data)
        time.sleep(0.005)  # 実デバイスのブロッキング write を模す

    def stop(self):
        pass

    def close(self):
        self.closed = True


class ScriptedSource:
    """トラックごとに決まったチャンク列を返すフェイク。"""

    def __init__(self, tracks, stall_on=None):
        self.tracks = tracks
        self.stall_on = stall_on or set()
        self.opened = []

    def list_tracks(self):
        return [TrackRef(n) for n in sorted(self.tracks)]

    def open(self, n):
        self.opened.append(n)
        if n in self.stall_on:
            def gen():
                yield self.tracks[n][0]
                raise SourceStallError("scratch")
            return gen()
        return iter(self.tracks[n])

    def close(self):
        pass


def make_engine(events):
    stream = FakeStream()
    engine = PlaybackEngine(events.append, stream_factory=lambda: stream,
                            stall_timeout=1.0)
    return engine, stream


def finished(events):
    return any(isinstance(e, PlaybackFinished) for e in events)


def test_plays_all_tracks_in_order_and_finishes():
    events = []
    engine, stream = make_engine(events)
    src = ScriptedSource({1: make_chunks(3), 2: make_chunks(2)})
    engine.play(src, [1, 2])
    assert wait_until(lambda: finished(events))
    changed = [e.number for e in events if isinstance(e, TrackChanged)]
    assert changed == [1, 2]
    assert stream.written == 5 * CHUNK_BYTES
    assert stream.closed


def test_pause_stops_output():
    events = []
    engine, stream = make_engine(events)
    src = ScriptedSource({1: make_chunks(2000)})
    engine.play(src, [1])
    assert wait_until(lambda: stream.written > 0)
    engine.toggle_pause()
    time.sleep(0.05)  # 書き込み途中のチャンクを吐き切らせる
    written = stream.written
    time.sleep(0.2)
    assert stream.written == written
    engine.toggle_pause()
    assert wait_until(lambda: stream.written > written)
    engine.stop()


def test_next_track_jumps():
    events = []
    engine, stream = make_engine(events)
    src = ScriptedSource({1: make_chunks(2000), 2: make_chunks(2)})
    engine.play(src, [1, 2])
    assert wait_until(lambda: stream.written > 0)
    engine.next_track()
    assert wait_until(lambda: finished(events))
    assert src.opened == [1, 2]


def test_prev_on_first_track_restarts():
    events = []
    engine, stream = make_engine(events)
    src = ScriptedSource({1: make_chunks(2000), 2: make_chunks(2)})
    engine.play(src, [1, 2])
    assert wait_until(lambda: stream.written > 0)
    engine.prev_track()
    assert wait_until(lambda: src.opened == [1, 1])
    engine.stop()


def test_stalled_track_is_skipped():
    events = []
    engine, stream = make_engine(events)
    src = ScriptedSource({1: make_chunks(2), 2: make_chunks(2)},
                         stall_on={1})
    engine.play(src, [1, 2])
    assert wait_until(lambda: finished(events))
    skipped = [e.number for e in events if isinstance(e, TrackSkipped)]
    assert skipped == [1]


def test_engine_waits_for_slow_first_chunk():
    """コールドスタートのソースをエンジンが早々に諦めない。

    エンジン側にも独立した stall 判定があるため、ソースだけ待てるように
    しても、ここが短いと 1 曲目がスキップされる(実機で発生した不具合)。
    """
    events = []
    stream = FakeStream()

    class SlowStartSource(ScriptedSource):
        def open(self, n):
            self.opened.append(n)

            def gen():
                time.sleep(0.6)  # 最初のデータまで待たされる
                yield from self.tracks[n]

            return gen()

    engine = PlaybackEngine(events.append, stream_factory=lambda: stream,
                            stall_timeout=0.2, start_timeout=5.0)
    engine.play(SlowStartSource({1: make_chunks(2)}), [1])
    assert wait_until(lambda: finished(events))
    assert not any(isinstance(e, TrackSkipped) for e in events)
    assert stream.written == 2 * CHUNK_BYTES


def test_missing_sounddevice_names_the_likely_cause(monkeypatch):
    """依存が無いときは「何をすればいいか」まで言う。

    実機で、README の `python main.py` に従ってシステム Python で起動され、
    再生の瞬間だけ ModuleNotFoundError になる事故が起きた。sounddevice の
    import は再生開始まで遅延するため、起動・CD 検知・メタデータ表示までは
    正常に見えてしまう。画面に出る文言だけで原因に辿り着けるようにする。
    """
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    with pytest.raises(RuntimeError) as exc:
        default_stream_factory()
    message = str(exc.value)
    assert "sounddevice" in message
    assert ".venv/bin/python" in message


def test_stream_init_failure_posts_error():
    events = []

    def bad_factory():
        raise RuntimeError("no device")

    engine = PlaybackEngine(events.append, stream_factory=bad_factory)
    engine.play(ScriptedSource({1: make_chunks(1)}), [1])
    assert wait_until(
        lambda: any(isinstance(e, PlaybackError) for e in events))


def test_stop_is_responsive():
    events = []
    engine, stream = make_engine(events)
    src = ScriptedSource({1: make_chunks(5000)})
    engine.play(src, [1])
    assert wait_until(lambda: stream.written > 0)
    t0 = time.time()
    engine.stop()
    assert time.time() - t0 < 2.0
    assert not finished(events)
