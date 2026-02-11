import logging
import subprocess
import time
import os
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
        if self.process:
            self.stop()
            time.sleep(0.5)

        # デバイスパスの特定 (/dev/diskX -> /dev/rdiskX)
        raw_device = ""
        try:
            result = subprocess.check_output(["mount"]).decode()
            for line in result.splitlines():
                if drive_path in line:
                    dev_node = line.split()[0]
                    raw_device = dev_node.replace("/dev/disk", "/dev/rdisk")
                    break
        except: pass

        vlc_target = f"cdda://{raw_device}" if raw_device else f"cdda://{drive_path}"
        self.logger.info(f"Starting playback of {vlc_target}")
        
        cmd = [
            self.vlc_path,
            "-I", "dummy",
            "--extraintf", "rc",
            "--rc-fake-tty",
            vlc_target,
        ]
        
        try:
            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=open("vlc_stdout.log", "w"),
                stderr=open("vlc_stderr.log", "w")
            )
            time.sleep(5.0)
            self._send_command("volume 256")
            if track_num > 1:
                self._send_command(f"goto {track_num-1}")
        except Exception as e:
            self.logger.error(f"Failed to start VLC: {e}")

    def stop(self):
        if self.process:
            self._send_command("shutdown")
            time.sleep(0.2)
            if self.process and self.process.poll() is None:
                self.process.terminate()
            self.process = None

    def play(self): self._send_command("play")
    def pause(self): self._send_command("pause")
    def next_track(self):
        self._send_command("next")
        self.current_track_index += 1
    def prev_track(self):
        self._send_command("prev")
        if self.current_track_index > 1: self.current_track_index -= 1
    
    def get_track_index(self): return self.current_track_index
    def is_playing(self): return self.process is not None and self.process.poll() is None
    
    def eject_disc(self):
        self.stop()
        subprocess.run(["drutil", "eject"], check=False)
