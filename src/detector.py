import os
import time
import logging
from pathlib import Path

class CDDetector:
    """
    /Volumes ディレクトリを監視して、新しいボリュームのマウントを検知するクラス。
    ポーリング方式を採用し、確実に検知を行う。
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.base_path = Path("/Volumes")
        self.known_volumes = self._get_current_volumes()
        self.callback = None
        self._running = False

    def _get_current_volumes(self):
        if not self.base_path.exists():
            return set()
        # ドットファイルなどは除外
        return {p.name for p in self.base_path.iterdir() if not p.name.startswith('.')}

    def start_monitoring(self, callback):
        """
        UI側から定期的に呼ばれることを想定するか、
        あるいは内部でスレッドを持つかだが、
        今回はUIのメインループから check() を呼ぶ方式に合わせるため、
        ここではコールバックの登録のみ行う。
        """
        self.callback = callback
        self.known_volumes = self._get_current_volumes()
        self._running = True
        self.logger.info("CD Detector (Polling) ready.")

    def check(self):
        """
        定期的に呼び出すメソッド。
        差分があればコールバックを実行する。
        """
        if not self._running:
            return

        current_volumes = self._get_current_volumes()
        
        # 新しく追加されたボリューム (マウント)
        added = current_volumes - self.known_volumes
        # 削除されたボリューム (アンマウント)
        removed = self.known_volumes - current_volumes

        if added:
            for vol_name in added:
                vol_path = self.base_path / vol_name
                self.logger.info(f"Volume detected: {vol_path}")
                if self.callback:
                    self.callback("mount", str(vol_path))
        
        if removed:
            for vol_name in removed:
                vol_path = self.base_path / vol_name
                self.logger.info(f"Volume removed: {vol_path}")
                if self.callback:
                    self.callback("unmount", str(vol_path))

        self.known_volumes = current_volumes

    def stop_monitoring(self):
        self._running = False