import logging
import subprocess
import time
import os
import threading
import numpy as np
from pathlib import Path

class CDPlayer:
    def __init__(self, test_mode=False):
        self.logger = logging.getLogger(__name__)
        self.process = None
        self.vlc_path = "/Applications/VLC.app/Contents/MacOS/VLC"
        self.current_track_index = 1
        self.audio_files = []
        self.test_mode = test_mode
        
        # FFT設定
        self.fft_size = 512
        self._spectrum = np.zeros(256)
        self._stop_event = threading.Event()
        self._is_seeking = False # シーク中フラグ
        
        # 窓関数の事前計算 (Hamming)
        self.window = np.hamming(self.fft_size)
        
        self.start_time = time.time()
        self.analysis_thread = threading.Thread(target=self._analysis_loop, daemon=True)
        self.analysis_thread.start()

    def _send_command(self, command):
        if self.process and self.process.poll() is None:
            try:
                self.process.stdin.write(f"{command}\n".encode())
                self.process.stdin.flush()
            except: pass

    def _analysis_loop(self):
        while not self._stop_event.is_set():
            if self.is_playing() and not self._is_seeking and (self.test_mode or self.audio_files):
                try:
                    # ここで spectrum を更新する重い処理 (略)
                    elapsed = time.time() - self.start_time
                    
                    if self.test_mode:
                        duration = 10.0
                        freq = 20.0 * (20000.0 / 20.0) ** ((elapsed % duration) / duration)
                        t_samples = np.linspace(0, self.fft_size / 44100.0, self.fft_size, endpoint=False)
                        mono = np.sin(2 * np.pi * freq * t_samples)
                        fft_res = np.abs(np.fft.rfft(mono * self.window))[:256]
                        mag = fft_res / (self.fft_size / 4.0)
                    else:
                        idx = self.current_track_index - 1
                        if 0 <= idx < len(self.audio_files):
                            file_path = self.audio_files[idx]
                            sample_rate = 44100
                            read_size = 1024 
                            byte_offset = int(elapsed * sample_rate) * 4
                            byte_offset &= ~3
                            
                            if os.path.exists(file_path):
                                with open(file_path, "rb") as f:
                                    f.seek(byte_offset)
                                    data = f.read(read_size * 4)
                                    if len(data) == read_size * 4:
                                        samples = np.frombuffer(data, dtype=np.int16).reshape(-1, 2)
                                        full_mono = samples.mean(axis=1) / 32768.0
                                        
                                        mags = []
                                        for start in [0, 256, 512]:
                                            segment = full_mono[start : start + self.fft_size]
                                            fft_res = np.abs(np.fft.rfft(segment * self.window))[:256]
                                            mags.append(fft_res)
                                        
                                        mag = np.mean(mags, axis=0) / (self.fft_size / 4.0)
                                        mag = np.log10(mag * 25 + 1)
                                    else: mag = np.zeros(256)
                            else: mag = np.zeros(256)
                        else: mag = np.zeros(256)

                    # 時間方向の平滑化 (EMA: 0.4が新しいデータ、0.6が前回のデータ)
                    self._spectrum = self._spectrum * 0.6 + mag * 0.4
                except: pass
            else:
                self._spectrum = self._spectrum * 0.8 # 徐々に減衰
            time.sleep(0.025)

    def play_cd(self, drive_path=None, track_num=1):
        self._is_seeking = True # 解析を一時停止
        if not self.test_mode:
            raw_device = ""
            try:
                result = subprocess.check_output(["mount"]).decode()
                for line in result.splitlines():
                    if drive_path in line:
                        raw_device = line.split()[0].replace("/dev/disk", "/dev/rdisk")
                        break
            except: pass
            target = f"cdda://{raw_device}" if raw_device else f"cdda://{drive_path}"
            p = Path(drive_path)
            self.audio_files = sorted([str(f) for f in p.glob("*.aiff")])
        else:
            target = "sweep.wav"

        cmd = [self.vlc_path, "-I", "dummy", "--extraintf", "rc", "--rc-fake-tty", target]
        if self.process: self.stop()
        self.process = subprocess.Popen(cmd, stdin=subprocess.PIPE, 
                                      stdout=open("vlc_stdout.log", "w"),
                                      stderr=open("vlc_stderr.log", "w"))
        time.sleep(5.0) # VLC安定待ち
        self._send_command("volume 256")
        self.start_time = time.time()
        self.current_track_index = track_num
        self._is_seeking = False # 解析再開

    def stop(self):
        if self.process:
            self._send_command("shutdown")
            self.process.terminate()
            self.process = None

    def play(self): self._send_command("play")
    def pause(self): self._send_command("pause")
    
    def _track_change_delay(self):
        self._is_seeking = True
        time.sleep(2.0) # トラック変更時のドライブ安定待ち
        self.start_time = time.time()
        self._is_seeking = False

    def next_track(self):
        self._send_command("next")
        self.current_track_index += 1
        threading.Thread(target=self._track_change_delay, daemon=True).start()

    def prev_track(self):
        self._send_command("prev")
        if self.current_track_index > 1: self.current_track_index -= 1
        threading.Thread(target=self._track_change_delay, daemon=True).start()
    
    def get_track_index(self): return self.current_track_index
    def is_playing(self): return self.process is not None and self.process.poll() is None
    def get_spectrum(self): return self._spectrum.tolist()

    def eject_disc(self):
        self.stop()
        subprocess.run(["drutil", "eject"], check=False)
