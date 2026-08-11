"""cdp エントリポイント。各コンポーネントを組み立てて起動する。"""
import logging
import logging.handlers
import sys
import tkinter as tk

from src.audio.engine import PlaybackEngine
from src.audio.sources import create_source
from src.core.controller import AppController
from src.disc.monitor import create_monitor
from src.disc.toc import TocReader
from src.metadata.fetcher import MetadataService
from src.ui.view import View

VERSION = "0.4.0"


def setup_logging():
    file_handler = logging.handlers.RotatingFileHandler(
        "cdp.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout), file_handler])
    for noisy in ("musicbrainzngs", "requests", "urllib3", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)


def main():
    setup_logging()
    logging.info("cdp %s starting", VERSION)

    root = tk.Tk()
    root.title("cdp")

    # engine → controller は post 経由の循環依存になるため遅延束縛する
    controller_ref = []

    def post_event(event):
        controller_ref[0].post(event)

    engine = PlaybackEngine(post_event=post_event)
    controller = AppController(
        toc_reader=TocReader(),
        engine=engine,
        metadata_service=MetadataService(),
        source_factory=create_source)
    controller_ref.append(controller)

    view = View(root, controller)
    monitor = create_monitor(controller.post)
    monitor.start()

    def on_quit():
        monitor.stop()
        engine.stop()

    view.set_on_quit(on_quit)
    root.mainloop()


if __name__ == "__main__":
    main()
