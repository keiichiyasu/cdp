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


from pathlib import Path

from src.audio.sources import CdparanoiaSource, SourceStallError

FAKE_BIN = str(Path(__file__).parent / "bin" / "fake_cdparanoia")


def test_cdparanoia_list_tracks():
    src = CdparanoiaSource(device="/dev/null", binary=FAKE_BIN)
    tracks = src.list_tracks()
    assert [t.number for t in tracks] == [1]


def test_cdparanoia_open_reads_pcm():
    src = CdparanoiaSource(device="/dev/null", binary=FAKE_BIN)
    data = b"".join(src.open(1))
    src.close()
    assert data == b"\x01\x02" * 4096


def test_cdparanoia_stall_raises(monkeypatch):
    monkeypatch.setenv("FAKE_CDPARANOIA_STALL", "1")
    src = CdparanoiaSource(device="/dev/null", binary=FAKE_BIN,
                           stall_timeout=0.3)
    with pytest.raises(SourceStallError):
        b"".join(src.open(1))
    src.close()
