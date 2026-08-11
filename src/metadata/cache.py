"""ディスク単位のメタデータキャッシュ(既定: ~/.cache/cdp/<disc_id>/)。"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from src.core.events import AlbumMeta, TrackMeta

logger = logging.getLogger(__name__)


class MetadataCache:
    def __init__(self, root: Path | None = None):
        self.root = Path(root) if root else Path.home() / ".cache" / "cdp"

    def _dir(self, disc_id: str) -> Path:
        return self.root / disc_id

    def load(self, disc_id: str) -> AlbumMeta | None:
        path = self._dir(disc_id) / "metadata.json"
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            tracks = tuple(TrackMeta(**t) for t in data["tracks"])
            title = data["title"]
            artist = data["artist"]
        except (OSError, KeyError, TypeError, json.JSONDecodeError):
            logger.warning("キャッシュが壊れています: %s", disc_id)
            return None
        cover = self._dir(disc_id) / "cover.jpg"
        return AlbumMeta(
            title=title, artist=artist, tracks=tracks,
            cover_path=str(cover) if cover.exists() else None)

    def store(self, disc_id: str, album: AlbumMeta,
              cover_bytes: bytes | None = None) -> AlbumMeta:
        d = self._dir(disc_id)
        d.mkdir(parents=True, exist_ok=True)
        data = {
            "title": album.title,
            "artist": album.artist,
            "tracks": [{"number": t.number, "title": t.title}
                       for t in album.tracks],
        }
        (d / "metadata.json").write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        cover_path = None
        if cover_bytes:
            (d / "cover.jpg").write_bytes(cover_bytes)
            cover_path = str(d / "cover.jpg")
        return AlbumMeta(album.title, album.artist, album.tracks, cover_path)
