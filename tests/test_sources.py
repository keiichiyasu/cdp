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


def test_cdparanoia_read_command_prefers_low_latency():
    """再生はリアルタイム優先なので paranoia 検証を無効化する。

    実機(Raspberry Pi 4 + USB ドライブ)での計測:
    paranoia 有効だと最初の音まで 2.9〜7.0 秒かかり、無効(-Z)なら 1.3 秒。
    さらに傷ディスクでは、有効だとリトライが stall 検知に達してトラックごと
    スキップされるが、無効なら軽微なノイズを出しつつ再生を継続できる。
    """
    argv = CdparanoiaSource(device="/dev/sr0").read_command(3)
    assert "-Z" in argv, "paranoia を無効にしていない"
    assert "-r" in argv, "raw リトルエンディアン PCM を要求していない"
    assert argv[-2:] == ["3", "-"], "トラック指定と stdout 出力が末尾にない"


def test_cdparanoia_stall_raises(monkeypatch):
    monkeypatch.setenv("FAKE_CDPARANOIA_STALL", "1")
    src = CdparanoiaSource(device="/dev/null", binary=FAKE_BIN,
                           stall_timeout=0.3)
    with pytest.raises(SourceStallError):
        b"".join(src.open(1))
    src.close()


import soundfile as sf
import struct

from src.audio.sources import AiffFileSource, TrackSourceError


def make_aiff(path, frames=1000):
    data = struct.pack("<h", 1000) * (frames * 2)  # int16 ステレオ
    with sf.SoundFile(str(path), "w", samplerate=44100, channels=2,
                      subtype="PCM_16", format="AIFF") as f:
        f.buffer_write(data, dtype="int16")


def test_aiff_list_tracks_numeric_order(tmp_path):
    make_aiff(tmp_path / "1 Audio Track.aiff")
    make_aiff(tmp_path / "2 Audio Track.aiff")
    make_aiff(tmp_path / "10 Audio Track.aiff")
    src = AiffFileSource(str(tmp_path))
    nums = [t.number for t in src.list_tracks()]
    assert nums == [1, 2, 10]  # 辞書順(1,10,2)ではなく数値順


def test_aiff_open_reads_pcm(tmp_path):
    make_aiff(tmp_path / "1 Audio Track.aiff", frames=1000)
    src = AiffFileSource(str(tmp_path))
    data = b"".join(src.open(1))
    src.close()
    assert len(data) == 1000 * 4  # 1000 フレーム * 4 バイト


def test_aiff_empty_dir_raises(tmp_path):
    with pytest.raises(TrackSourceError):
        AiffFileSource(str(tmp_path)).list_tracks()
