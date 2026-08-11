"""ディスク検知(OS 別)。専用スレッドで 2 秒間隔ポーリング。"""
from __future__ import annotations

import logging
import os
import sys
import threading
from pathlib import Path

from src.core.events import DiscInserted, DiscRemoved, NotAudioCd

logger = logging.getLogger(__name__)

# linux/cdrom.h の定数
CDROM_DRIVE_STATUS = 0x5326
CDROM_DISC_STATUS = 0x5327
CDS_NO_DISC = 1
CDS_DISC_OK = 4
CDS_AUDIO = 100
CDS_MIXED = 105


class BaseMonitor:
    def __init__(self, post_event, interval: float = 2.0):
        self._post = post_event
        self._interval = interval
        self._stop_flag = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_flag.set()

    def _loop(self) -> None:
        while not self._stop_flag.is_set():
            try:
                self.poll_once()
            except Exception:
                logger.exception("ディスク検知ポーリングに失敗")
            self._stop_flag.wait(self._interval)

    def poll_once(self) -> None:
        raise NotImplementedError


class LinuxDiscMonitor(BaseMonitor):
    """ioctl(CDROM_DRIVE_STATUS) でメディアの有無を正確に判定する。"""

    def __init__(self, post_event, device: str = "/dev/sr0",
                 interval: float = 2.0, status_fn=None):
        super().__init__(post_event, interval)
        self.device = device
        self._status_fn = status_fn or self._read_status
        self._had_disc = False

    def poll_once(self) -> None:
        drive_status, disc_status = self._status_fn()
        has_disc = drive_status == CDS_DISC_OK
        if has_disc and not self._had_disc:
            if disc_status in (CDS_AUDIO, CDS_MIXED):
                logger.info("オーディオ CD 挿入: %s", self.device)
                self._post(DiscInserted(self.device))
            else:
                logger.info("非オーディオディスク挿入: %s", self.device)
                self._post(NotAudioCd(self.device))
        elif not has_disc and self._had_disc:
            logger.info("ディスク取り出し: %s", self.device)
            self._post(DiscRemoved(self.device))
        self._had_disc = has_disc

    def _read_status(self) -> tuple[int, int]:
        import fcntl
        fd = os.open(self.device, os.O_RDONLY | os.O_NONBLOCK)
        try:
            drive_status = fcntl.ioctl(fd, CDROM_DRIVE_STATUS, 0)
            disc_status = -1
            if drive_status == CDS_DISC_OK:
                disc_status = fcntl.ioctl(fd, CDROM_DISC_STATUS, 0)
            return drive_status, disc_status
        finally:
            os.close(fd)


class MacDiscMonitor(BaseMonitor):
    """/Volumes を監視し、.aiff を含むボリュームをオーディオ CD とみなす。

    非オーディオボリューム(USB メモリ等)は無視する。既知集合に入れず
    毎回確認し直すことで、マウント直後に .aiff が見えないケースにも耐える。
    """

    def __init__(self, post_event, volumes_root: str = "/Volumes",
                 interval: float = 2.0):
        super().__init__(post_event, interval)
        self._root = Path(volumes_root)
        self._known: set[str] = set()  # 通知済みのオーディオ CD ボリューム名

    def poll_once(self) -> None:
        current = {p.name for p in self._root.iterdir() if p.is_dir()}
        for name in sorted(self._known - current):
            self._known.discard(name)
            self._post(DiscRemoved(str(self._root / name)))
        for name in sorted(current - self._known):
            if any((self._root / name).glob("*.aiff")):
                self._known.add(name)
                self._post(DiscInserted(str(self._root / name)))


def create_monitor(post_event, device: str | None = None,
                   interval: float = 2.0):
    """OS に応じた DiscMonitor を返すファクトリ。"""
    if sys.platform == "darwin":
        return MacDiscMonitor(post_event, interval=interval)
    if sys.platform.startswith("linux"):
        return LinuxDiscMonitor(post_event, device=device or "/dev/sr0",
                                interval=interval)
    raise NotImplementedError(f"Unsupported platform: {sys.platform}")
