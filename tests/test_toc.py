from types import SimpleNamespace

import pytest

from src.disc.toc import TocError, TocReader, resolve_mac_raw_device


def fake_disc():
    return SimpleNamespace(
        id="abc123",
        tracks=[SimpleNamespace(number=1, sectors=15000),
                SimpleNamespace(number=2, sectors=22500)])


def test_toc_reader_success():
    reader = TocReader(read_fn=lambda d=None: fake_disc(),
                       sleep_fn=lambda s: None)
    info = reader.read("/dev/sr0")
    assert info.disc_id == "abc123"
    assert [t.number for t in info.tracks] == [1, 2]
    assert info.tracks[0].duration == pytest.approx(200.0)


def test_toc_reader_retries_then_fails():
    calls = []

    def bad(d=None):
        calls.append(d)
        raise RuntimeError("cannot read table of contents")

    reader = TocReader(read_fn=bad, sleep_fn=lambda s: None, attempts=3)
    with pytest.raises(TocError):
        reader.read("/dev/sr0")
    assert len(calls) == 3


def test_toc_reader_succeeds_after_retry():
    state = {"n": 0}

    def flaky(d=None):
        state["n"] += 1
        if state["n"] < 3:
            raise RuntimeError("busy")
        return fake_disc()

    reader = TocReader(read_fn=flaky, sleep_fn=lambda s: None)
    assert reader.read("/dev/sr0").disc_id == "abc123"


def test_resolve_mac_raw_device():
    out = ("/dev/disk4s1 on /Volumes/Audio CD "
           "(cddafs, local, nodev, nosuid, read-only)\n")
    assert resolve_mac_raw_device("/Volumes/Audio CD", out) == "/dev/rdisk4s1"


def test_resolve_mac_raw_device_not_found():
    assert resolve_mac_raw_device("/Volumes/Nope", "") is None
