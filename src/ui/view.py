"""全画面 View(レイアウト A)。状態スナップショットを描くだけでロジックを持たない。"""
from __future__ import annotations

import logging
import tkinter as tk
from pathlib import Path

from PIL import Image, ImageTk

from src.core.events import AppState, ViewState

logger = logging.getLogger(__name__)

POLL_MS = 200
BG = "#000000"
FG_MAIN = "#e6e6e6"
FG_SUB = "#8c8c8c"

PLACEHOLDER = (Path(__file__).resolve().parent.parent.parent
               / "assets" / "placeholder.png")


def format_track_line(vs: ViewState) -> str:
    if vs.state is AppState.FINISHED:
        return "再生終了"
    if vs.track_number is None:
        return ""
    title = vs.track_title or f"トラック {vs.track_number}"
    return f"{vs.track_number}. {title}"


def format_artist_line(vs: ViewState) -> str:
    parts = []
    if vs.artist:
        parts.append(vs.artist)
    if vs.album_title:
        parts.append(vs.album_title)
    line = " — ".join(parts)
    if vs.track_number is not None and vs.track_total:
        counter = f"{vs.track_number} / {vs.track_total}"
        line = f"{line}   {counter}" if line else counter
    return line


class View:
    def __init__(self, root: tk.Tk, controller):
        self._root = root
        self._controller = controller
        self._last: ViewState | None = None
        self._photo = None       # PhotoImage の参照保持(GC 対策)
        self._photo_key = None
        self._on_quit = None

        root.configure(bg=BG)
        root.attributes("-fullscreen", True)
        root.config(cursor="none")

        h = root.winfo_screenheight()
        self._art_size = int(h * 0.70)
        font_main = ("Helvetica", max(int(h * 0.033), 20), "bold")
        font_sub = ("Helvetica", max(int(h * 0.022), 14))

        self._art_label = tk.Label(root, bg=BG)
        self._art_label.place(relx=0.5, rely=0.42, anchor="center")
        self._line1 = tk.Label(root, bg=BG, fg=FG_MAIN, font=font_main)
        self._line1.place(relx=0.5, rely=0.85, anchor="center")
        self._line2 = tk.Label(root, bg=BG, fg=FG_SUB, font=font_sub)
        self._line2.place(relx=0.5, rely=0.92, anchor="center")

        # 開発用の隠しキー操作
        root.bind("<Escape>", lambda e: self._quit())
        root.bind("<space>", lambda e: controller.toggle_pause())
        root.bind("n", lambda e: controller.next_track())
        root.bind("p", lambda e: controller.prev_track())
        root.bind("e", lambda e: controller.eject())

        root.after(POLL_MS, self._tick)

    def set_on_quit(self, fn) -> None:
        self._on_quit = fn

    def _quit(self) -> None:
        if self._on_quit is not None:
            self._on_quit()
        self._root.destroy()

    def _tick(self) -> None:
        try:
            vs = self._controller.process_pending()
            if vs != self._last:
                self._render(vs)
                self._last = vs
        except Exception:
            logger.exception("描画に失敗")
        self._root.after(POLL_MS, self._tick)

    def _render(self, vs: ViewState) -> None:
        if vs.state is AppState.NO_DISC:
            self._show_art(None, small=True)
            self._line1.config(text="")
            self._line2.config(text="CD を入れてください")
        elif vs.state is AppState.READING:
            self._show_art(None, small=True)
            self._line1.config(text="")
            self._line2.config(text="読み込み中...")
        elif vs.state in (AppState.PLAYING, AppState.FINISHED):
            self._show_art(vs.cover_path)
            self._line1.config(text=format_track_line(vs))
            self._line2.config(text=format_artist_line(vs))
        elif vs.state is AppState.ERROR:
            self._show_art(None, small=True)
            self._line1.config(text="")
            self._line2.config(text=vs.error_message or "エラーが発生しました")

    def _show_art(self, cover_path: str | None, small: bool = False) -> None:
        path = cover_path or str(PLACEHOLDER)
        size = int(self._art_size * (0.35 if small else 1.0))
        key = (path, size)
        if key == self._photo_key:
            return
        try:
            img = Image.open(path)
            img.thumbnail((size, size), Image.Resampling.LANCZOS)
            self._photo = ImageTk.PhotoImage(img)
            self._art_label.config(image=self._photo)
            self._photo_key = key
        except Exception:
            logger.exception("画像を表示できません: %s", path)
