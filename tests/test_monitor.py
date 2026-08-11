import shutil

from src.core.events import DiscInserted, DiscRemoved, NotAudioCd
from src.disc.monitor import (CDS_AUDIO, CDS_DISC_OK, CDS_NO_DISC,
                              LinuxDiscMonitor, MacDiscMonitor)

CDS_DATA_1 = 101  # linux/cdrom.h: データディスク


class Poster:
    def __init__(self):
        self.events = []

    def __call__(self, event):
        self.events.append(event)


def seq_status(*pairs):
    """poll_once ごとに順に返す (drive_status, disc_status) 列。"""
    it = iter(pairs)
    state = {"last": pairs[-1]}

    def fn():
        try:
            state["last"] = next(it)
        except StopIteration:
            pass
        return state["last"]

    return fn


def test_linux_audio_disc_cycle():
    post = Poster()
    mon = LinuxDiscMonitor(post, device="/dev/sr0",
                           status_fn=seq_status(
                               (CDS_NO_DISC, -1),
                               (CDS_DISC_OK, CDS_AUDIO),
                               (CDS_DISC_OK, CDS_AUDIO),
                               (CDS_NO_DISC, -1)))
    for _ in range(4):
        mon.poll_once()
    assert post.events == [DiscInserted("/dev/sr0"),
                           DiscRemoved("/dev/sr0")]


def test_linux_data_disc_reports_not_audio():
    post = Poster()
    mon = LinuxDiscMonitor(post, device="/dev/sr0",
                           status_fn=seq_status(
                               (CDS_DISC_OK, CDS_DATA_1),
                               (CDS_DISC_OK, CDS_DATA_1)))
    mon.poll_once()
    mon.poll_once()
    assert post.events == [NotAudioCd("/dev/sr0")]  # 1 回だけ


def test_mac_detects_audio_volume(tmp_path):
    post = Poster()
    mon = MacDiscMonitor(post, volumes_root=str(tmp_path))
    mon.poll_once()  # 空の状態
    vol = tmp_path / "Audio CD"
    vol.mkdir()
    (vol / "1 Audio Track.aiff").write_bytes(b"x")
    mon.poll_once()
    assert post.events == [DiscInserted(str(vol))]
    shutil.rmtree(vol)
    mon.poll_once()
    assert post.events == [DiscInserted(str(vol)), DiscRemoved(str(vol))]


def test_mac_ignores_non_audio_volume(tmp_path):
    post = Poster()
    mon = MacDiscMonitor(post, volumes_root=str(tmp_path))
    (tmp_path / "USBSTICK").mkdir()
    mon.poll_once()
    mon.poll_once()
    assert post.events == []


def test_mac_detects_disc_present_at_startup(tmp_path):
    vol = tmp_path / "Audio CD"
    vol.mkdir()
    (vol / "1 Audio Track.aiff").write_bytes(b"x")
    post = Poster()
    mon = MacDiscMonitor(post, volumes_root=str(tmp_path))
    mon.poll_once()
    assert post.events == [DiscInserted(str(vol))]  # 起動時挿入済みも再生対象
