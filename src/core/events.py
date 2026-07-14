"""アプリ全体で使う状態・イベント・ViewState の定義。"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class AppState(Enum):
    NO_DISC = auto()
    READING = auto()
    PLAYING = auto()
    FINISHED = auto()
    ERROR = auto()


@dataclass(frozen=True)
class TrackRef:
    number: int
    duration: float | None = None  # 秒。不明なら None


@dataclass(frozen=True)
class DiscInfo:
    disc_id: str | None
    tracks: tuple[TrackRef, ...]


@dataclass(frozen=True)
class TrackMeta:
    number: int
    title: str


@dataclass(frozen=True)
class AlbumMeta:
    title: str
    artist: str
    tracks: tuple[TrackMeta, ...]
    cover_path: str | None = None


# --- コントローラへ送るイベント ---

@dataclass(frozen=True)
class DiscInserted:
    device: str  # Linux: /dev/sr0, macOS: /Volumes/<名前>


@dataclass(frozen=True)
class DiscRemoved:
    device: str


@dataclass(frozen=True)
class NotAudioCd:
    device: str


@dataclass(frozen=True)
class TocReady:
    disc: DiscInfo
    generation: int = 0  # 古いワーカー結果を捨てるための世代番号


@dataclass(frozen=True)
class TocFailed:
    message: str
    generation: int = 0


@dataclass(frozen=True)
class TrackChanged:
    number: int


@dataclass(frozen=True)
class TrackSkipped:
    number: int


@dataclass(frozen=True)
class PlaybackFinished:
    pass


@dataclass(frozen=True)
class PlaybackError:
    message: str


@dataclass(frozen=True)
class MetadataReady:
    album: AlbumMeta
    generation: int = 0


@dataclass(frozen=True)
class MetadataFailed:
    message: str
    generation: int = 0


@dataclass(frozen=True)
class ViewState:
    state: AppState
    track_number: int | None = None
    track_total: int | None = None
    track_title: str | None = None
    album_title: str | None = None
    artist: str | None = None
    cover_path: str | None = None
    error_message: str | None = None
