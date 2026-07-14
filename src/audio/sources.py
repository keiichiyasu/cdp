"""トラック供給源(プラットフォーム別)。PCM は 44.1kHz/16bit/2ch/LE 固定。"""
from __future__ import annotations

import logging
import os
import re
import select
import subprocess
import sys
from pathlib import Path
from typing import Iterator

from src.core.events import TrackRef

logger = logging.getLogger(__name__)

CD_SAMPLE_RATE = 44100
CD_CHANNELS = 2
CD_BYTES_PER_FRAME = 4  # int16 * 2ch
CHUNK_FRAMES = 4096
CHUNK_BYTES = CHUNK_FRAMES * CD_BYTES_PER_FRAME


class SourceStallError(Exception):
    """読み取りが停止した(傷ディスク等)。"""


class TrackSourceError(Exception):
    """トラックの列挙・オープンに失敗した。"""


_TOC_LINE = re.compile(r"^\s*(\d+)\.\s+(\d+)\s")


def parse_cdparanoia_toc(text: str) -> list[TrackRef]:
    """`cdparanoia -Q` の出力からトラック一覧を得る。セクタ数 / 75 = 秒。"""
    tracks = []
    for line in text.splitlines():
        m = _TOC_LINE.match(line)
        if m:
            tracks.append(TrackRef(number=int(m.group(1)),
                                   duration=int(m.group(2)) / 75.0))
    return tracks


class CdparanoiaSource:
    """Linux: cdparanoia の子プロセスから raw PCM を読む。"""

    def __init__(self, device: str = "/dev/sr0", binary: str = "cdparanoia",
                 stall_timeout: float = 10.0):
        self.device = device
        self.binary = binary
        self.stall_timeout = stall_timeout
        self._proc: subprocess.Popen | None = None

    def list_tracks(self) -> list[TrackRef]:
        result = subprocess.run(
            [self.binary, "-Q", "-d", self.device],
            capture_output=True, text=True, timeout=60)
        tracks = parse_cdparanoia_toc(result.stderr)
        if not tracks:
            raise TrackSourceError("cdparanoia -Q でトラックを列挙できません")
        return tracks

    def open(self, track_no: int) -> Iterator[bytes]:
        self.close()
        # -r: raw リトルエンディアン PCM を stdout へ
        self._proc = subprocess.Popen(
            [self.binary, "-q", "-r", "-d", self.device, str(track_no), "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        return self._read_chunks(self._proc)

    def _read_chunks(self, proc: subprocess.Popen) -> Iterator[bytes]:
        fd = proc.stdout.fileno()
        while True:
            ready, _, _ = select.select([fd], [], [], self.stall_timeout)
            if not ready:
                raise SourceStallError(
                    f"cdparanoia ({self.device}): {self.stall_timeout} 秒無応答")
            data = os.read(fd, CHUNK_BYTES)
            if not data:
                return
            yield data

    def close(self) -> None:
        if self._proc is not None:
            self._proc.terminate()
            try:
                self._proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self._proc.kill()
            self._proc = None


_AIFF_NUM = re.compile(r"^(\d+)")


class AiffFileSource:
    """macOS: マウントされたオーディオ CD の .aiff ファイルを読む。"""

    def __init__(self, mount_path: str):
        self.mount_path = Path(mount_path)
        self._file = None

    def _paths(self) -> dict[int, Path]:
        found = {}
        for p in self.mount_path.glob("*.aiff"):
            m = _AIFF_NUM.match(p.name)
            if m:
                found[int(m.group(1))] = p
        return found

    def list_tracks(self) -> list[TrackRef]:
        import soundfile as sf
        paths = self._paths()
        if not paths:
            raise TrackSourceError(f"{self.mount_path} に .aiff がありません")
        tracks = []
        for num in sorted(paths):
            with sf.SoundFile(str(paths[num])) as f:
                tracks.append(TrackRef(number=num,
                                       duration=len(f) / f.samplerate))
        return tracks

    def open(self, track_no: int) -> Iterator[bytes]:
        import soundfile as sf
        self.close()
        paths = self._paths()
        if track_no not in paths:
            raise TrackSourceError(f"トラック {track_no} がありません")
        self._file = sf.SoundFile(str(paths[track_no]))
        return self._read_chunks(self._file)

    def _read_chunks(self, f) -> Iterator[bytes]:
        while True:
            buf = f.buffer_read(CHUNK_FRAMES, dtype="int16")
            if len(buf) == 0:
                return
            yield bytes(buf)

    def close(self) -> None:
        if self._file is not None:
            self._file.close()
            self._file = None


def create_source(device: str):
    """OS に応じた TrackSource を返す。device は DiscInserted.device と同じ値。"""
    if sys.platform == "darwin":
        return AiffFileSource(device)
    return CdparanoiaSource(device)
