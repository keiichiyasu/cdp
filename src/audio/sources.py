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
