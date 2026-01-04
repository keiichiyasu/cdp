import logging
import subprocess
import time
import os
import re
import threading
from pathlib import Path

class CDPlayer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.process = None
        # Linux用のVLCパスに変更
        self.vlc_path = "vlc" 
        self.current_track_index = 1
        
        # 'which' コマンドでVLCの存在を確認
        if subprocess.run(["which", self.vlc_path], capture_output=True).returncode != 0:
            self.logger.error(f"VLC command not found. Please install VLC media player.")

    def _send_command(self, command):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(f"{command}\n".encode())
                self.process.stdin.flush()
            except Exception as e:
                self.logger.error(f"Failed to send command to VLC: {e}")

    def play_cd(self, drive_path="/dev/cdrom", track_num=1):
        """
        Linux環境でCDを再生する。
        drive_path: /dev/cdrom などのデバイスパス。
        """
        if self.process:
            self.stop()
            time.sleep(0.5)

        if not os.path.exists(drive_path):
            self.logger.error(f"CD device not found at: {drive_path}")
            return

        self.logger.info(f"Starting playback of track {track_num} from {drive_path}...")
        
        # VLCをcddaプロトコルで起動
        media_path = f"cdda://{drive_path}"
        
        cmd = [
            self.vlc_path,
            "-I", "dummy", # GUIなしで起動
            "--extraintf", "rc", # RCインターフェースを有効化
            "--rc-fake-tty",
            media_path
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            time.sleep(2.0) # 起動待ち
            self._send_command("volume 256")
            if track_num > 1:
                # RCインターフェースでは seek <track_number> (1-indexed)
                self._send_command(f"seek {track_num}")
                
        except Exception as e:
            self.logger.error(f"Failed to start VLC: {e}")

    def stop(self):
        if self.process:
            self._send_command("shutdown")
            try:
                time.sleep(0.2)
                if self.process.poll() is None:
                    self.process.terminate()
            except:
                if self.process: self.process.kill()
            self.process = None

    def play(self): self._send_command("play")
    def pause(self): self._send_command("pause")
    def next_track(self):
        self.logger.info("Sending next command")
        self._send_command("next")
        self.current_track_index += 1

    def prev_track(self):
        self.logger.info("Sending prev command")
        self._send_command("prev")
        if self.current_track_index > 1:
            self.current_track_index -= 1
    
    def is_playing(self):
        return self.process is not None and self.process.poll() is None
    
    def eject_disc(self):
        self.stop()
        # Linux用のejectコマンド
        subprocess.run(["eject"], check=False)
