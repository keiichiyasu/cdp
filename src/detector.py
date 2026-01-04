import os
import time
import logging
from pathlib import Path

class CDDetector:
    """
    Linux環境でCD-ROMドライブの状態を監視するクラス。
    /dev/cdrom の存在をポーリングして検知する。
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.cdrom_path = Path("/dev/cdrom")
        self.cd_was_present = self._is_cd_present()
        self.callback = None
        self._running = False

    def _is_cd_present(self):
        """ /dev/cdrom が存在し、それがシンボリックリンクであればCDありと判断 """
        return self.cdrom_path.is_symlink() or self.cdrom_path.exists()

    def start_monitoring(self, callback):
        self.callback = callback
        self.cd_was_present = self._is_cd_present()
        self._running = True
        self.logger.info("CD Detector (Linux Polling) ready.")

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

    def stop_monitoring(self):
        self._running = False