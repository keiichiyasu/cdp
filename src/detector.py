import os
import sys
import time
import logging
from pathlib import Path
import glob

class CDDetector:
    """A base class for CD detection."""
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.callback = None
        self._running = False

    def start_monitoring(self, callback):
        self.callback = callback
        self._running = True

    def check(self):
        raise NotImplementedError

    def stop_monitoring(self):
        self._running = False

class CDDetectorMac(CDDetector):
    """
    macOSでCDドライブの状態を監視するクラス。
    /Volumes ディレクトリの変更をポーリングして検知する。
    """
    def __init__(self):
        super().__init__()
        self.volumes_path = Path("/Volumes")
        self.previous_volumes = self._get_current_volumes()
        self.logger.info("CD Detector (macOS Polling) ready.")

    def _get_current_volumes(self):
        """現在の/Volumes内のディレクトリ一覧を取得する"""
        # "Macintosh HD"のようなシステムボリュームは除外
        return set(p.name for p in self.volumes_path.iterdir() if p.is_dir() and p.name != "Macintosh HD")

    def start_monitoring(self, callback):
        super().start_monitoring(callback)
        self.previous_volumes = self._get_current_volumes()

    def check(self):
        if not self._running:
            return

        current_volumes = self._get_current_volumes()
        new_volumes = current_volumes - self.previous_volumes
        removed_volumes = self.previous_volumes - current_volumes

        for volume_name in new_volumes:
            # TODO: これが本当にオーディオCDかどうかのチェックを追加する
            self.logger.info(f"CD detected: {volume_name}")
            if self.callback:
                self.callback("mount", str(self.volumes_path / volume_name))

        for volume_name in removed_volumes:
            self.logger.info(f"CD removed: {volume_name}")
            if self.callback:
                self.callback("unmount", str(self.volumes_path / volume_name))

        self.previous_volumes = current_volumes

class CDDetectorLinux(CDDetector):
    """
    Linux環境でCD-ROMドライブの状態を監視するクラス。
    /dev/cdrom の存在をポーリングして検知する。
    """
    def __init__(self):
        super().__init__()
        self.cdrom_path = Path("/dev/cdrom")
        self.cd_was_present = self._is_cd_present()
        self.logger.info("CD Detector (Linux Polling) ready.")

    def _is_cd_present(self):
        """ /dev/cdrom が存在し、それがシンボリックリンクであればCDありと判断 """
        return self.cdrom_path.is_symlink() or self.cdrom_path.exists()

    def start_monitoring(self, callback):
        super().start_monitoring(callback)
        self.cd_was_present = self._is_cd_present()

    def check(self):
        """
        定期的に呼び出すメソッド。
        CDの有無に変化があればコールバックを実行する。
        """
        if not self._running:
            return

        cd_is_present = self._is_cd_present()
        
        if cd_is_present and not self.cd_was_present:
            # CDが挿入された
            self.logger.info(f"CD detected: {self.cdrom_path}")
            if self.callback:
                # Linuxではマウントポイントを直接渡す代わりにデバイスパスを渡す
                self.callback("mount", str(self.cdrom_path))
        
        elif not cd_is_present and self.cd_was_present:
            # CDが取り出された
            self.logger.info(f"CD removed: {self.cdrom_path}")
            if self.callback:
                self.callback("unmount", str(self.cdrom_path))

        self.cd_was_present = cd_is_present

def get_detector():
    """OSに応じて適切なCDDetectorのインスタンスを返すファクトリ関数"""
    if sys.platform == "darwin":
        return CDDetectorMac()
    elif sys.platform.startswith("linux"):
        return CDDetectorLinux()
    else:
        raise NotImplementedError(f"Unsupported platform: {sys.platform}")
