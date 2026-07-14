import pytest

from src.audio.sources import parse_cdparanoia_toc

CDPARANOIA_Q_OUTPUT = """\
cdparanoia III release 10.2 (September 11, 2008)

Table of contents (audio tracks only):
track        length               begin        copy pre ch
===========================================================
  1.    16831 [03:44.31]        0 [00:00.00]    no   no  2
  2.    20995 [04:39.70]    16831 [03:44.31]    no   no  2
TOTAL   37826 [08:24.26]    (audio only)
"""


def test_parse_cdparanoia_toc():
    tracks = parse_cdparanoia_toc(CDPARANOIA_Q_OUTPUT)
    assert [t.number for t in tracks] == [1, 2]
    assert tracks[0].duration == pytest.approx(16831 / 75.0)


def test_parse_cdparanoia_toc_empty():
    assert parse_cdparanoia_toc("no disc\n") == []
