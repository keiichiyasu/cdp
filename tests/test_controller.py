from src.audio.sources import TrackSourceError
from src.core.controller import AppController
from src.core.events import (AlbumMeta, AppState, DiscInfo, DiscInserted,
                             DiscRemoved, NotAudioCd, PlaybackError,
                             PlaybackFinished, TrackChanged, TrackMeta,
                             TrackRef)
from src.disc.toc import TocError

DISC = DiscInfo("abc123", (TrackRef(1, 200.0), TrackRef(2, 180.0)))
ALBUM = AlbumMeta("Kind of Blue", "Miles Davis",
                  (TrackMeta(1, "So What"), TrackMeta(2, "Freddie Freeloader")))


class FakeEngine:
    def __init__(self):
        self.calls = []

    def play(self, source, tracks):
        self.calls.append(("play", tracks))

    def stop(self):
        self.calls.append(("stop",))

    def toggle_pause(self):
        self.calls.append(("pause",))

    def next_track(self):
        self.calls.append(("next",))

    def prev_track(self):
        self.calls.append(("prev",))


class FakeSource:
    def __init__(self, fail=False):
        self.fail = fail
        self.closed = False

    def list_tracks(self):
        if self.fail:
            raise TrackSourceError("boom")
        return [TrackRef(1), TrackRef(2)]

    def open(self, n):
        return iter(())

    def close(self):
        self.closed = True


class FakeToc:
    def __init__(self, disc=DISC, error=False):
        self.disc = disc
        self.error = error

    def read(self, device):
        if self.error:
            raise TocError("no toc")
        return self.disc


class FakeMeta:
    def __init__(self, album=None, error=False):
        self.album = album
        self.error = error
        self.calls = []

    def get(self, disc_id, fallback_title=None):
        self.calls.append((disc_id, fallback_title))
        if self.error:
            raise RuntimeError("net down")
        return self.album


def make_controller(toc=None, meta=None, source=None, eject=None,
                    now_fn=None, run_async=None):
    engine = FakeEngine()
    source = source or FakeSource()
    c = AppController(
        toc_reader=toc or FakeToc(),
        engine=engine,
        metadata_service=meta or FakeMeta(),
        source_factory=lambda device: source,
        run_async=run_async or (lambda fn: fn()),
        eject_fn=eject or (lambda: None),
        now_fn=now_fn or (lambda: 0.0),
    )
    return c, engine, source


def test_insert_starts_playback_immediately():
    c, engine, _ = make_controller()
    c.post(DiscInserted("/dev/sr0"))
    vs = c.process_pending()
    assert vs.state is AppState.PLAYING
    assert ("play", [1, 2]) in engine.calls
    assert vs.track_number == 1
    assert vs.track_total == 2


def test_metadata_fills_view_state():
    c, _, _ = make_controller(meta=FakeMeta(album=ALBUM))
    c.post(DiscInserted("/dev/sr0"))
    vs = c.process_pending()
    assert vs.album_title == "Kind of Blue"
    assert vs.artist == "Miles Davis"
    assert vs.track_title == "So What"


def test_metadata_failure_keeps_playing():
    c, _, _ = make_controller(meta=FakeMeta(error=True))
    c.post(DiscInserted("/dev/sr0"))
    vs = c.process_pending()
    assert vs.state is AppState.PLAYING
    assert vs.album_title is None


def test_toc_failure_falls_back_to_source_tracks():
    c, engine, _ = make_controller(toc=FakeToc(error=True),
                                   meta=FakeMeta(album=ALBUM))
    c.post(DiscInserted("/dev/sr0"))
    vs = c.process_pending()
    assert vs.state is AppState.PLAYING
    assert ("play", [1, 2]) in engine.calls
    assert vs.album_title is None  # DiscID なしなのでメタデータ検索しない


def test_toc_and_source_failure_shows_error():
    c, _, _ = make_controller(toc=FakeToc(error=True),
                              source=FakeSource(fail=True))
    c.post(DiscInserted("/dev/sr0"))
    vs = c.process_pending()
    assert vs.state is AppState.ERROR


def test_removal_stops_and_resets():
    c, engine, source = make_controller()
    c.post(DiscInserted("/dev/sr0"))
    c.process_pending()
    c.post(DiscRemoved("/dev/sr0"))
    vs = c.process_pending()
    assert vs.state is AppState.NO_DISC
    assert ("stop",) in engine.calls
    assert source.closed


def test_not_audio_cd():
    c, _, _ = make_controller()
    c.post(NotAudioCd("/dev/sr0"))
    vs = c.process_pending()
    assert vs.state is AppState.ERROR
    assert "オーディオ" in vs.error_message


def test_track_change_updates_view():
    c, _, _ = make_controller()
    c.post(DiscInserted("/dev/sr0"))
    c.process_pending()
    c.post(TrackChanged(2))
    assert c.process_pending().track_number == 2


def test_finished_state():
    c, _, _ = make_controller()
    c.post(DiscInserted("/dev/sr0"))
    c.process_pending()
    c.post(PlaybackFinished())
    assert c.process_pending().state is AppState.FINISHED


def test_playback_error_then_retry_after_30s():
    clock = [0.0]
    c, engine, _ = make_controller(now_fn=lambda: clock[0])
    c.post(DiscInserted("/dev/sr0"))
    c.process_pending()
    c.post(PlaybackError("device lost"))
    assert c.process_pending().state is AppState.ERROR
    clock[0] = 29.0
    assert c.process_pending().state is AppState.ERROR
    clock[0] = 31.0
    vs = c.process_pending()
    assert vs.state is AppState.PLAYING
    assert engine.calls.count(("play", [1, 2])) == 2


def test_stale_toc_result_ignored_after_removal():
    jobs = []
    c, _, _ = make_controller(run_async=jobs.append)
    c.post(DiscInserted("/dev/sr0"))
    c.process_pending()  # READING、TOC ジョブは未実行
    c.post(DiscRemoved("/dev/sr0"))
    c.process_pending()  # NO_DISC
    jobs[0]()  # 古い TOC 結果が今ごろ届く
    assert c.process_pending().state is AppState.NO_DISC


def test_no_disc_id_skips_metadata_lookup():
    meta = FakeMeta(album=ALBUM)
    c, _, _ = make_controller(
        toc=FakeToc(disc=DiscInfo(None, (TrackRef(1),))), meta=meta)
    c.post(DiscInserted("/dev/sr0"))
    c.process_pending()
    assert meta.calls == []


def test_mac_volume_name_used_as_fallback_title():
    meta = FakeMeta(album=ALBUM)
    c, _, _ = make_controller(meta=meta)
    c.post(DiscInserted("/Volumes/Kind of Blue"))
    c.process_pending()
    assert meta.calls == [("abc123", "Kind of Blue")]


def test_eject_stops_engine_and_runs_command():
    ejected = []
    c, engine, _ = make_controller(eject=lambda: ejected.append(True))
    c.post(DiscInserted("/dev/sr0"))
    c.process_pending()
    c.eject()
    assert ("stop",) in engine.calls
    assert ejected == [True]


def test_user_commands_only_while_playing():
    c, engine, _ = make_controller()
    c.toggle_pause()
    c.next_track()
    c.prev_track()
    assert engine.calls == []  # NO_DISC 中は何もしない
