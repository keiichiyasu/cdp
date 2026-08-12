"""PCM 再生エンジン。再生位置・トラック番号はここが所有する。"""
from __future__ import annotations

import logging
import queue
import threading
import time

from src.audio.sources import (CD_BYTES_PER_FRAME, CD_CHANNELS,
                               CD_SAMPLE_RATE, SourceStallError)
from src.core.events import (PlaybackError, PlaybackFinished, TrackChanged,
                             TrackSkipped)

logger = logging.getLogger(__name__)

PREFETCH_CHUNKS = 86  # ≒ 8 秒分 (44100 * 8 / 4096)


def default_stream_factory():
    # import はここまで遅延させている(テストや macOS 開発時に PortAudio を
    # 必須にしないため)。その代わり依存漏れが再生の瞬間まで表面化しないので、
    # 失敗時は原因と対処をそのまま画面に出せる文言にしておく。
    try:
        import sounddevice as sd
    except ImportError as e:
        raise RuntimeError(
            "sounddevice を読み込めません。venv の Python で起動してください "
            "(.venv/bin/python main.py)") from e
    return sd.RawOutputStream(samplerate=CD_SAMPLE_RATE,
                              channels=CD_CHANNELS, dtype="int16")


class _Prefetcher:
    """ソースを先読みしてキュー(リングバッファ)に貯める。"""

    _EOF = object()

    def __init__(self, chunks, max_chunks: int):
        self._queue: queue.Queue = queue.Queue(maxsize=max_chunks)
        self._error: Exception | None = None
        self._abort = threading.Event()
        self._thread = threading.Thread(target=self._fill, args=(chunks,),
                                        daemon=True)
        self._thread.start()

    def _fill(self, chunks) -> None:
        try:
            for chunk in chunks:
                if not self._put(chunk):
                    return
            self._put(self._EOF)
        except Exception as e:  # SourceStallError 等はここで捕まえて伝搬する
            self._error = e
            self._put(self._EOF)

    def _put(self, item) -> bool:
        while not self._abort.is_set():
            try:
                self._queue.put(item, timeout=0.2)
                return True
            except queue.Full:
                continue
        return False

    def get(self, timeout: float):
        """次のチャンク。EOF なら None。ソース側エラーなら raise。
        タイムアウトは queue.Empty を送出する。"""
        item = self._queue.get(timeout=timeout)
        if item is self._EOF:
            if self._error is not None:
                raise self._error
            return None
        return item

    def stop(self) -> None:
        self._abort.set()
        try:
            while True:
                self._queue.get_nowait()
        except queue.Empty:
            pass
        self._thread.join(timeout=3)


class PlaybackEngine:
    def __init__(self, post_event, stream_factory=default_stream_factory,
                 stall_timeout: float = 12.0, start_timeout: float = 60.0):
        """stall_timeout は再生中の音切れ、start_timeout は最初の音までの待ち。

        ソース側の同名の値に対する保険。ソースが待てるようにしても、ここが
        短いままだとコールドスタート時に 1 曲目がスキップされる。
        """
        self._post = post_event
        self._stream_factory = stream_factory
        self._stall_timeout = stall_timeout
        self._start_timeout = start_timeout
        self._thread: threading.Thread | None = None
        self._stop_flag = threading.Event()
        self._paused = threading.Event()
        self._lock = threading.Lock()
        self._jump: int | None = None  # 次に再生するトラックのリスト内 index
        self._index = 0
        self._tracks: list[int] = []
        self._frames_played = 0

    # --- 公開 API(どのスレッドから呼んでも安全) ---

    def play(self, source, track_numbers: list[int]) -> None:
        self.stop()
        self._tracks = list(track_numbers)
        if not self._tracks:
            self._post(PlaybackFinished())
            return
        self._stop_flag.clear()
        self._paused.clear()
        self._jump = 0
        self._thread = threading.Thread(target=self._run, args=(source,),
                                        daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_flag.set()
        self._paused.clear()
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None

    def toggle_pause(self) -> None:
        if self._paused.is_set():
            self._paused.clear()
        else:
            self._paused.set()

    def next_track(self) -> None:
        with self._lock:
            if self._index + 1 < len(self._tracks):
                self._jump = self._index + 1

    def prev_track(self) -> None:
        with self._lock:
            self._jump = max(self._index - 1, 0)

    @property
    def position_seconds(self) -> float:
        return self._frames_played / CD_SAMPLE_RATE

    # --- 再生スレッド ---

    def _run(self, source) -> None:
        try:
            stream = self._stream_factory()
            stream.start()
        except Exception as e:
            logger.exception("音声ストリームを開けません")
            self._post(PlaybackError(f"音声デバイスを開けません: {e}"))
            return
        try:
            while not self._stop_flag.is_set():
                with self._lock:
                    if self._jump is None:
                        break  # 進む先がない = 全トラック終了
                    self._index = self._jump
                    self._jump = None
                    track_no = self._tracks[self._index]
                self._frames_played = 0
                self._post(TrackChanged(track_no))
                self._play_one(source, track_no, stream)
                if self._stop_flag.is_set():
                    return
                with self._lock:
                    if self._jump is None and self._index + 1 < len(self._tracks):
                        self._jump = self._index + 1
            self._post(PlaybackFinished())
        except Exception as e:
            logger.exception("再生スレッドが異常終了しました")
            self._post(PlaybackError(str(e)))
        finally:
            try:
                source.close()
            finally:
                stream.stop()
                stream.close()

    def _play_one(self, source, track_no: int, stream) -> None:
        """1 トラックを再生する。読み取り停止はスキップとして扱う。"""
        try:
            chunks = source.open(track_no)
        except Exception as e:
            logger.warning("トラック %d を開けません: %s", track_no, e)
            self._post(TrackSkipped(track_no))
            return
        pre = _Prefetcher(chunks, PREFETCH_CHUNKS)
        first = True
        try:
            while True:
                if self._stop_flag.is_set():
                    return
                with self._lock:
                    if self._jump is not None:
                        return
                if self._paused.is_set():
                    time.sleep(0.05)
                    continue
                chunk = self._next_chunk(pre, track_no, first)
                if chunk is None:
                    return  # トラック終端 or 停止/ジャンプ要求
                first = False
                stream.write(chunk)
                self._frames_played += len(chunk) // CD_BYTES_PER_FRAME
        except SourceStallError as e:
            logger.warning("%s — トラックをスキップします", e)
            self._post(TrackSkipped(track_no))
        finally:
            pre.stop()

    def _next_chunk(self, pre: _Prefetcher, track_no: int,
                    first: bool = False):
        limit = self._start_timeout if first else self._stall_timeout
        deadline = time.monotonic() + limit
        while True:
            if self._stop_flag.is_set():
                return None
            with self._lock:
                if self._jump is not None:
                    return None
            try:
                return pre.get(timeout=0.2)
            except queue.Empty:
                if time.monotonic() > deadline:
                    raise SourceStallError(
                        f"トラック {track_no}: 読み取りが {limit} 秒停止")
