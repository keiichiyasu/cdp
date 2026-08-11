"""MusicBrainz / Cover Art Archive からのメタデータ取得。

ここの関数はすべてブロッキング。必ずワーカースレッドから呼ぶこと。
"""
from __future__ import annotations

import logging

import musicbrainzngs
import requests

from src.core.events import AlbumMeta, TrackMeta
from src.metadata.cache import MetadataCache

logger = logging.getLogger(__name__)

APP_NAME = "cdp"
APP_VERSION = "0.4.0"
APP_CONTACT = "https://github.com/keiichiyasu/cdp"


def parse_release(release: dict) -> AlbumMeta:
    """MusicBrainz のリリース dict を AlbumMeta に変換する。"""
    artist = "Unknown Artist"
    if release.get("artist-credit"):
        artist = release["artist-credit"][0]["artist"]["name"]
    raw_tracks = []
    if "medium-list" in release:
        for medium in release["medium-list"]:
            raw_tracks.extend(medium.get("track-list", []))
    elif "track-list" in release:
        raw_tracks = release["track-list"]
    tracks = []
    for i, t in enumerate(raw_tracks, start=1):
        try:
            number = int(t.get("position", i))
        except (TypeError, ValueError):
            number = i
        title = t.get("recording", {}).get("title") or f"トラック {number}"
        tracks.append(TrackMeta(number=number, title=title))
    return AlbumMeta(title=release.get("title", "Unknown Album"),
                     artist=artist, tracks=tuple(tracks))


class MetadataFetcher:
    def __init__(self):
        musicbrainzngs.set_useragent(APP_NAME, APP_VERSION, APP_CONTACT)

    def fetch(self, disc_id: str, fallback_title: str | None = None):
        """(AlbumMeta, release_id) を返す。見つからなければ None。"""
        try:
            result = musicbrainzngs.get_releases_by_discid(
                disc_id, includes=["artists", "recordings"])
            if "disc" in result and result["disc"].get("release-list"):
                release = result["disc"]["release-list"][0]
                return parse_release(release), release.get("id")
        except musicbrainzngs.ResponseError:
            logger.info("DiscID %s は MusicBrainz に未登録", disc_id)
        except musicbrainzngs.WebServiceError as e:
            logger.warning("MusicBrainz エラー: %s", e)
            return None
        if fallback_title and fallback_title != "Audio CD":
            return self._search_by_title(fallback_title)
        return None

    def _search_by_title(self, title: str):
        try:
            result = musicbrainzngs.search_releases(release=title, limit=1)
            if result["release-list"]:
                release_id = result["release-list"][0]["id"]
                full = musicbrainzngs.get_release_by_id(
                    release_id, includes=["artists", "recordings"])
                return parse_release(full["release"]), release_id
        except musicbrainzngs.WebServiceError as e:
            logger.warning("タイトル検索に失敗: %s", e)
        return None

    def fetch_cover(self, release_id: str) -> bytes | None:
        url = f"https://coverartarchive.org/release/{release_id}/front"
        try:
            resp = requests.get(
                url, timeout=15,
                headers={"User-Agent": f"{APP_NAME}/{APP_VERSION}"})
            resp.raise_for_status()
            return resp.content
        except requests.RequestException as e:
            logger.info("カバーアートなし: %s", e)
            return None


class MetadataService:
    """キャッシュ優先でメタデータを取得する(ブロッキング。ワーカーで呼ぶ)。"""

    def __init__(self, cache: MetadataCache | None = None, fetcher=None):
        self._cache = cache or MetadataCache()
        self._fetcher = fetcher or MetadataFetcher()

    def get(self, disc_id: str | None,
            fallback_title: str | None = None) -> AlbumMeta | None:
        if not disc_id:
            return None
        cached = self._cache.load(disc_id)
        if cached is not None:
            logger.info("メタデータキャッシュヒット: %s", disc_id)
            return cached
        found = self._fetcher.fetch(disc_id, fallback_title)
        if found is None:
            return None
        album, release_id = found
        cover = self._fetcher.fetch_cover(release_id) if release_id else None
        return self._cache.store(disc_id, album, cover)
