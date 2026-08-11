from src.core.events import TrackMeta
from src.metadata.cache import MetadataCache
from src.metadata.fetcher import MetadataService, parse_release

RELEASE = {
    "id": "rel-1",
    "title": "Kind of Blue",
    "artist-credit": [{"artist": {"name": "Miles Davis"}}],
    "medium-list": [{"track-list": [
        {"position": "1", "recording": {"title": "So What"}},
        {"position": "2", "recording": {"title": "Freddie Freeloader"}},
    ]}],
}


def test_parse_release():
    album = parse_release(RELEASE)
    assert album.title == "Kind of Blue"
    assert album.artist == "Miles Davis"
    assert album.tracks == (TrackMeta(1, "So What"),
                            TrackMeta(2, "Freddie Freeloader"))


def test_parse_release_missing_fields():
    album = parse_release({"title": "X",
                           "track-list": [{}, {}]})
    assert album.artist == "Unknown Artist"
    assert album.tracks == (TrackMeta(1, "トラック 1"),
                            TrackMeta(2, "トラック 2"))


class FakeFetcher:
    def __init__(self, album=None):
        self.album = album
        self.fetch_calls = 0

    def fetch(self, disc_id, fallback_title=None):
        self.fetch_calls += 1
        return (self.album, "rel-1") if self.album else None

    def fetch_cover(self, release_id):
        return b"img"


def test_service_fetches_then_caches(tmp_path):
    album = parse_release(RELEASE)
    fetcher = FakeFetcher(album)
    service = MetadataService(cache=MetadataCache(root=tmp_path),
                              fetcher=fetcher)
    first = service.get("abc123")
    assert first.title == "Kind of Blue"
    assert first.cover_path is not None
    second = service.get("abc123")
    assert second == first
    assert fetcher.fetch_calls == 1  # 2 回目はキャッシュヒット


def test_service_not_found(tmp_path):
    service = MetadataService(cache=MetadataCache(root=tmp_path),
                              fetcher=FakeFetcher(album=None))
    assert service.get("abc123") is None


def test_service_no_disc_id(tmp_path):
    fetcher = FakeFetcher()
    service = MetadataService(cache=MetadataCache(root=tmp_path),
                              fetcher=fetcher)
    assert service.get(None) is None
    assert fetcher.fetch_calls == 0
