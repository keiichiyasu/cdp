"""discid による TOC(DiscID・トラック数・トラック長)の読み取り。"""
from __future__ import annotations

import logging
import subprocess
import sys
import time

from src.core.events import DiscInfo, TrackRef

logger = logging.getLogger(__name__)


class TocError(Exception):
    """リトライしても TOC を読めなかった。"""


def resolve_mac_raw_device(mount_path: str, mount_output: str) -> str | None:
    """`mount` コマンド出力からマウントパスに対応する raw デバイスを探す。"""
    for line in mount_output.splitlines():
        parts = line.split(" on ")
        if len(parts) == 2 and parts[1].startswith(mount_path + " "):
            return parts[0].replace("/dev/disk", "/dev/rdisk")
    return None


class TocReader:
    def __init__(self, read_fn=None, sleep_fn=time.sleep, attempts: int = 3):
        if read_fn is None:
            import discid
            read_fn = discid.read
        self._read_fn = read_fn
        self._sleep = sleep_fn
        self._attempts = attempts

    def read(self, device: str) -> DiscInfo:
        """DiscInfo を返す。失敗時は TocError(再生は妨げないこと)。"""
        target = self._resolve(device)
        last_error: Exception | None = None
        for attempt in range(self._attempts):
            try:
                disc = self._read_fn(target) if target else self._read_fn()
                tracks = tuple(
                    TrackRef(number=t.number, duration=t.sectors / 75.0)
                    for t in disc.tracks)
                logger.info("DiscID: %s (%d tracks)", disc.id, len(tracks))
                return DiscInfo(disc_id=disc.id, tracks=tracks)
            except Exception as e:
                last_error = e
                logger.warning("TOC 読み取り %d 回目失敗: %s", attempt + 1, e)
                self._sleep(0.5 * (2 ** attempt))
        raise TocError(str(last_error))

    def _resolve(self, device: str) -> str | None:
        if sys.platform == "darwin" and device.startswith("/Volumes"):
            out = subprocess.run(["mount"], capture_output=True,
                                 text=True).stdout
            resolved = resolve_mac_raw_device(device, out)
            logger.info("%s -> raw device %s", device, resolved)
            return resolved
        return device
