from pathlib import Path

from src.core.events import AlbumMeta, TrackMeta
from src.metadata.cache import MetadataCache

ALBUM = AlbumMeta("Kind of Blue", "Miles Davis",
                  (TrackMeta(1, "So What"), TrackMeta(2, "Freddie Freeloader")))


def test_roundtrip_with_cover(tmp_path):
    cache = MetadataCache(root=tmp_path)
    stored = cache.store("abc123", ALBUM, cover_bytes=b"jpegdata")
    assert stored.cover_path is not None
    assert Path(stored.cover_path).read_bytes() == b"jpegdata"
    assert cache.load("abc123") == stored


def test_roundtrip_without_cover(tmp_path):
    cache = MetadataCache(root=tmp_path)
    stored = cache.store("abc123", ALBUM, cover_bytes=None)
    assert stored.cover_path is None
    assert cache.load("abc123") == stored


def test_miss_returns_none(tmp_path):
    assert MetadataCache(root=tmp_path).load("zzz") is None


def test_broken_json_returns_none(tmp_path):
    d = tmp_path / "abc123"
    d.mkdir()
    (d / "metadata.json").write_text("{not json", encoding="utf-8")
    assert MetadataCache(root=tmp_path).load("abc123") is None
