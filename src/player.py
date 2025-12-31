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
        self.vlc_path = "/Applications/VLC.app/Contents/MacOS/VLC"
        self.current_track_index = 1
        
        if not os.path.exists(self.vlc_path):
            self.logger.error(f"VLC application not found at {self.vlc_path}")

    def _send_command(self, command):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(f"{command}\n".encode())
                self.process.stdin.flush()
            except Exception as e:
                self.logger.error(f"Failed to send command to VLC: {e}")

    def play_cd(self, drive_path=None, track_num=1):
        """
        macOSのマウントポイント内のファイルを再生する。
        drive_path: /Volumes/Love SQ などのマウントパス。
        """
        if self.process:
            self.stop()
            time.sleep(0.5)

        if not drive_path or not os.path.exists(drive_path):
            self.logger.error(f"Drive path not found: {drive_path}")
            return

        # マウントポイント内のオーディオファイルを探す
        # macOSでは通常 .aiff ファイルとして見える
        p = Path(drive_path)
        audio_files = sorted([str(f) for f in p.glob("*.aiff")])
        if not audio_files:
            audio_files = sorted([str(f) for f in p.glob("*.wav")])
            
        if not audio_files:
            self.logger.error(f"No audio files found in {drive_path}")
            # フォールバックとして従来のcdda://も一応試すが期待薄
            return

        self.logger.info(f"Found {len(audio_files)} tracks. Starting playback of track {track_num}...")
        
        # VLCを起動し、全トラックをプレイリストに追加
        # GUIを表示させてデバッグする
        cmd = [
            self.vlc_path,
            "-I", "macosx", # 標準のmacOSインターフェースを使用
            # "--rc-fake-tty", # macosxインターフェースと競合する可能性があるので一旦外すか、rcを追加で指定する
            "--extraintf", "rc", # 追加インターフェースとしてRCを有効化
            "--rc-fake-tty",
            "--aout", "coreaudio",
        ] + audio_files # 全ファイルを引数に渡す
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            time.sleep(2.0) # GUI起動待ち
            self._send_command("volume 256")
            # 指定トラックへ移動 (gotoコマンド)
            if track_num > 1:
                self._send_command(f"goto {track_num-1}")
                
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
        subprocess.run(["drutil", "eject"], check=False)
