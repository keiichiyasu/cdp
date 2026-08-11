"""状態機械。すべてのイベントはここで一元処理される。

process_pending() は View(Tk メインループ)から定期的に呼ばれる。
post() はどのスレッドから呼んでもよい。
"""
from __future__ import annotations

import logging
import os
import queue
import subprocess
import sys
import threading
import time

from src.core.events import (AppState, DiscInfo, DiscInserted, DiscRemoved,
                             MetadataFailed, MetadataReady, NotAudioCd,
                             PlaybackError, PlaybackFinished, TocFailed,
                             TocReady, TrackChanged, TrackSkipped, ViewState)

logger = logging.getLogger(__name__)

RETRY_AFTER_SECONDS = 30.0  # 音声デバイス失敗後の再試行間隔


def run_in_thread(fn) -> None:
    threading.Thread(target=fn, daemon=True).start()


def default_eject() -> None:
    cmd = ["drutil", "eject"] if sys.platform == "darwin" else ["eject"]
    subprocess.run(cmd, check=False, timeout=30)


class AppController:
    def __init__(self, toc_reader, engine, metadata_service, source_factory,
                 run_async=run_in_thread, eject_fn=default_eject,
                 now_fn=time.monotonic):
        self._toc_reader = toc_reader
        self._engine = engine
        self._metadata = metadata_service
        self._source_factory = source_factory
        self._run_async = run_async
        self._eject_fn = eject_fn
        self._now = now_fn
        self._queue: queue.Queue = queue.Queue()

        self._state = AppState.NO_DISC
        self._generation = 0
        self._device: str | None = None
        self._disc: DiscInfo | None = None
        self._album = None
        self._track_number: int | None = None
        self._error: str | None = None
        self._source = None
        self._retry_at: float | None = None

    # --- どのスレッドからでも呼べる入口 ---

    def post(self, event) -> None:
        self._queue.put(event)

    # --- View(Tk メインループ)から定期的に呼ぶ ---

    def process_pending(self) -> ViewState:
        while True:
            try:
                event = self._queue.get_nowait()
            except queue.Empty:
                break
            self._handle(event)
        self._maybe_retry()
        return self._view_state()

    # --- View からの操作(開発用キー) ---

    def toggle_pause(self) -> None:
        if self._state is AppState.PLAYING:
            self._engine.toggle_pause()

    def next_track(self) -> None:
        if self._state is AppState.PLAYING:
            self._engine.next_track()

    def prev_track(self) -> None:
        if self._state is AppState.PLAYING:
            self._engine.prev_track()

    def eject(self) -> None:
        self._engine.stop()
        try:
            self._eject_fn()
        except Exception:
            logger.exception("イジェクトに失敗")
        # 取り出し自体の検知は DiscMonitor に任せる(DiscRemoved で NO_DISC へ)

    # --- イベント処理 ---

    def _handle(self, event) -> None:
        if isinstance(event, DiscInserted):
            self._on_inserted(event.device)
        elif isinstance(event, DiscRemoved):
            self._engine.stop()
            self._reset()
        elif isinstance(event, NotAudioCd):
            self._engine.stop()
            self._reset()
            self._state = AppState.ERROR
            self._error = "オーディオ CD ではありません"
        elif isinstance(event, TocReady):
            if (event.generation == self._generation
                    and self._state is AppState.READING):
                self._on_toc(event.disc)
        elif isinstance(event, TocFailed):
            if (event.generation == self._generation
                    and self._state is AppState.READING):
                self._state = AppState.ERROR
                self._error = "このディスクを読み取れません"
        elif isinstance(event, TrackChanged):
            if self._state is AppState.PLAYING:
                self._track_number = event.number
        elif isinstance(event, TrackSkipped):
            logger.warning("トラック %d をスキップ(読み取り不能)", event.number)
        elif isinstance(event, PlaybackFinished):
            if self._state is AppState.PLAYING:
                self._state = AppState.FINISHED
        elif isinstance(event, PlaybackError):
            if self._state is AppState.PLAYING:
                self._engine.stop()
                self._state = AppState.ERROR
                self._error = event.message
                if self._disc is not None:
                    self._retry_at = self._now() + RETRY_AFTER_SECONDS
        elif isinstance(event, MetadataReady):
            if event.generation == self._generation and self._disc is not None:
                self._album = event.album
        elif isinstance(event, MetadataFailed):
            logger.info("メタデータ取得失敗(再生には影響なし): %s",
                        event.message)

    def _on_inserted(self, device: str) -> None:
        self._engine.stop()
        self._reset()
        self._device = device
        self._state = AppState.READING
        self._source = self._source_factory(device)
        gen = self._generation
        source = self._source
        reader = self._toc_reader

        def job():
            try:
                disc = reader.read(device)
            except Exception as e:
                logger.warning("TOC 読み取り失敗(%s)。ソースに切替", e)
                try:
                    tracks = tuple(source.list_tracks())
                    disc = DiscInfo(disc_id=None, tracks=tracks)
                except Exception as e2:
                    self.post(TocFailed(str(e2), generation=gen))
                    return
            self.post(TocReady(disc, generation=gen))

        self._run_async(job)

    def _on_toc(self, disc: DiscInfo) -> None:
        self._disc = disc
        self._start_playback()
        if disc.disc_id:
            gen = self._generation
            disc_id = disc.disc_id
            fallback = self._fallback_title()
            service = self._metadata

            def job():
                try:
                    album = service.get(disc_id, fallback)
                except Exception as e:
                    self.post(MetadataFailed(str(e), generation=gen))
                    return
                if album is None:
                    self.post(MetadataFailed("not found", generation=gen))
                else:
                    self.post(MetadataReady(album, generation=gen))

            self._run_async(job)

    def _start_playback(self) -> None:
        disc = self._disc
        self._state = AppState.PLAYING
        self._error = None
        self._retry_at = None
        numbers = [t.number for t in disc.tracks]
        self._track_number = numbers[0] if numbers else None
        self._engine.play(self._source, numbers)

    def _maybe_retry(self) -> None:
        if (self._retry_at is not None and self._state is AppState.ERROR
                and self._disc is not None and self._now() >= self._retry_at):
            logger.info("再生を再試行します")
            self._start_playback()

    def _fallback_title(self) -> str | None:
        if self._device and self._device.startswith("/Volumes/"):
            return os.path.basename(self._device)
        return None

    def _reset(self) -> None:
        self._generation += 1
        self._state = AppState.NO_DISC
        self._device = None
        self._disc = None
        self._album = None
        self._track_number = None
        self._error = None
        self._retry_at = None
        if self._source is not None:
            try:
                self._source.close()
            except Exception:
                logger.exception("ソースのクローズに失敗")
            self._source = None

    def _view_state(self) -> ViewState:
        track_title = None
        album_title = None
        artist = None
        cover = None
        total = len(self._disc.tracks) if self._disc else None
        if self._album is not None:
            album_title = self._album.title
            artist = self._album.artist
            cover = self._album.cover_path
            if self._track_number is not None:
                for t in self._album.tracks:
                    if t.number == self._track_number:
                        track_title = t.title
                        break
        return ViewState(
            state=self._state,
            track_number=self._track_number,
            track_total=total,
            track_title=track_title,
            album_title=album_title,
            artist=artist,
            cover_path=cover,
            error_message=self._error,
        )
