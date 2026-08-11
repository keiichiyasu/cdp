"""結合テスト: 実 AiffFileSource + 実 PlaybackEngine + 実 AppController。

他のテストは run_async を同期実行に差し替えているため、本番と同じ
「TOC 読取をワーカースレッドで回す」経路はここでしか通らない。
音声デバイスだけフェイクにする。
"""
import struct

import soundfile as sf

from src.audio.engine import PlaybackEngine
from src.audio.sources import AiffFileSource
from src.core.controller import AppController
from src.core.events import AppState, DiscInserted, DiscRemoved
from src.disc.toc import TocError
from tests.support import wait_until

TRACK_SECONDS = 0.2


class FakeStream:
    def __init__(self):
        self.written = 0

    def start(self):
        pass

    def write(self, data):
        self.written += len(data)

    def stop(self):
        pass

    def close(self):
        pass


class FailingToc:
    """DiscID を読めないディスクを模す(ソース列挙へのフォールバックを通す)。"""

    def read(self, device):
        raise TocError("no drive")


class NoMetadata:
    def get(self, disc_id, fallback_title=None):
        return None


def make_aiff(path, seconds=TRACK_SECONDS):
    frames = int(44100 * seconds)
    data = struct.pack("<h", 0) * (frames * 2)
    with sf.SoundFile(str(path), "w", samplerate=44100, channels=2,
                      subtype="PCM_16", format="AIFF") as f:
        f.buffer_write(data, dtype="int16")
    return frames


def test_insert_plays_all_tracks_then_finishes(tmp_path):
    total_frames = sum(make_aiff(tmp_path / f"{n} Audio Track.aiff")
                       for n in (1, 2, 3))

    stream = FakeStream()
    controller_ref = []
    engine = PlaybackEngine(post_event=lambda e: controller_ref[0].post(e),
                            stream_factory=lambda: stream)
    controller = AppController(
        toc_reader=FailingToc(),
        engine=engine,
        metadata_service=NoMetadata(),
        source_factory=lambda device: AiffFileSource(device))
    controller_ref.append(controller)

    controller.post(DiscInserted(str(tmp_path)))
    # TOC 読取はワーカースレッドなので、挿入直後はまだ READING
    assert controller.process_pending().state is AppState.READING

    assert wait_until(
        lambda: controller.process_pending().state is AppState.PLAYING)
    vs = controller.process_pending()
    assert vs.track_number == 1
    assert vs.track_total == 3

    assert wait_until(
        lambda: controller.process_pending().state is AppState.FINISHED,
        timeout=15.0)
    # 全トラック分の PCM がちょうど流れている(取りこぼし・重複なし)
    assert stream.written // 4 == total_frames

    controller.post(DiscRemoved(str(tmp_path)))
    assert controller.process_pending().state is AppState.NO_DISC
