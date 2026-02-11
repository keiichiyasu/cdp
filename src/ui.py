import customtkinter as ctk
import logging
from PIL import Image, ImageTk
import requests
from io import BytesIO
import random
import traceback
import threading
import time

from src.detector import CDDetector
from src.fetcher import MetadataFetcher
from src.player import CDPlayer

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class CDPApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CDP - CD Player")
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True) # 常に最前面
        self.bind("<Escape>", self.close_app)
        
        self.player = CDPlayer()
        self.fetcher = MetadataFetcher()
        self.detector = CDDetector() 
        self.current_metadata = None
        
        self._setup_ui()
        self.logger = logging.getLogger("CDP")

        self.logger.info("Application starting...")

        # 起動時にトレイを排出
        self.after(500, self.player.eject_disc)

        # 監視スレッドの開始 (UIスレッドをブロックしないように)
        threading.Thread(target=self._detector_thread, daemon=True).start()

        # UI更新ループ (ビジュアライザー等)
        self.after(100, self._update_loop)

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        self.main_frame = ctk.CTkFrame(self, fg_color="black")
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        self.art_label = ctk.CTkLabel(self.main_frame, text="Waiting for CD...", text_color="gray", font=("Helvetica", 24))
        self.art_label.grid(row=0, column=0, sticky="nsew")
        
        self.spectrum_canvas = ctk.CTkCanvas(self.main_frame, height=100, bg="black", highlightthickness=0)
        self.spectrum_canvas.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))

        self.controls_frame = ctk.CTkFrame(self, height=120, fg_color="#111111")
        self.controls_frame.grid(row=1, column=0, sticky="ew")
        self.controls_frame.grid_columnconfigure((0,1,2,3,4), weight=1)

        self.btn_eject = ctk.CTkButton(self.controls_frame, text="⏏", width=60, height=40, command=self._eject)
        self.btn_eject.grid(row=0, column=0, pady=10)

        self.btn_prev = ctk.CTkButton(self.controls_frame, text="⏮", width=60, height=40, command=self.player.prev_track)
        self.btn_prev.grid(row=0, column=1, pady=10)

        self.btn_play = ctk.CTkButton(self.controls_frame, text="⏯", width=80, height=40, command=self._toggle_play)
        self.btn_play.grid(row=0, column=2, pady=10)

        self.btn_next = ctk.CTkButton(self.controls_frame, text="⏭", width=60, height=40, command=self.player.next_track)
        self.btn_next.grid(row=0, column=3, pady=10)

        self.info_label = ctk.CTkLabel(self.controls_frame, text="Ready", font=("Helvetica", 18))
        self.info_label.grid(row=1, column=0, columnspan=5, pady=(0, 10))

    def _detector_thread(self):
        """バックグラウンドでCD検知を行うスレッド"""
        self.detector.start_monitoring(self._queue_cd_event)
        while True:
            try:
                self.detector.check()
            except Exception as e:
                print(f"Detector error: {e}")
            time.sleep(1)

    def _queue_cd_event(self, action, path):
        """スレッドから呼ばれ、UIスレッドにイベントを投げる"""
        self.after(0, lambda: self._on_cd_event(action, path))

    def _on_cd_event(self, action, path):
        self.logger.info(f"CD Event: {action} - {path}")
        if action == "mount":
            self.after(2000, lambda: self._handle_disc_insertion(path))
        elif action == "unmount":
            self.info_label.configure(text="No Disc")
            self.art_label.configure(image=None, text="Waiting for CD...")
            self.current_metadata = None

    def _handle_disc_insertion(self, path):
        self.info_label.configure(text="💿 Loading...")
        
        def task():
            try:
                disc_id = self.fetcher.get_disc_id(path)
                metadata = self.fetcher.fetch_metadata(disc_id)
                
                pil_img = None
                if metadata and metadata.get('cover_art_url'):
                    try:
                        resp = requests.get(metadata['cover_art_url'], timeout=10)
                        pil_img = Image.open(BytesIO(resp.content))
                        pil_img.load()
                    except: pass

                def update():
                    self.current_metadata = metadata
                    if metadata:
                        title = metadata['tracks'][0]['title'] if metadata['tracks'] else metadata['title']
                        self.info_label.configure(text=f"1. {title} - {metadata['artist']}")
                        if pil_img: self._show_image(pil_img)
                    else:
                        self.info_label.configure(text="Unknown Album")
                self.after(0, update)

                self.player.play_cd(drive_path=path)
                self.after(1000, self.focus_force)
            except Exception as e:
                self.logger.error(f"Task error: {e}")

        threading.Thread(target=task, daemon=True).start()

    def _show_image(self, pil_img):
        screen_h = self.winfo_screenheight()
        target_h = int(screen_h * 0.6)
        ratio = target_h / pil_img.height
        target_w = int(pil_img.width * ratio)
        ctk_img = ctk.CTkImage(light_image=pil_img, dark_image=pil_img, size=(target_w, target_h))
        self.art_label.configure(image=ctk_img, text="")
        self.current_image = ctk_img

    def _update_loop(self):
        if self.player.is_playing():
            self.spectrum_canvas.delete("all")
            w = self.spectrum_canvas.winfo_width()
            h = self.spectrum_canvas.winfo_height()
            
            # ビジュアライザー
            if not hasattr(self, '_bar_h'): self._bar_h = [0.0]*40
            for i in range(40):
                target = random.random() * h * 0.7
                self._bar_h[i] = self._bar_h[i]*0.6 + target*0.4
                self.spectrum_canvas.create_rectangle(i*20, h-self._bar_h[i], i*20+15, h, fill="#00ff00", outline="")
            
            # トラック更新
            if not hasattr(self, '_up_cnt'): self._up_cnt = 0
            self._up_cnt += 1
            if self._up_cnt > 20:
                self._up_cnt = 0
                if self.current_metadata and self.current_metadata['tracks']:
                    idx = self.player.get_track_index() - 1
                    if 0 <= idx < len(self.current_metadata['tracks']):
                        t = self.current_metadata['tracks'][idx]
                        self.info_label.configure(text=f"{t['number']}. {t['title']} - {self.current_metadata['artist']}")

        self.after(50, self._update_loop)

    def _toggle_play(self):
        if self.player.is_playing(): self.player.pause()
        else: self.player.play()

    def _eject(self):
        self.player.eject_disc()
        self.info_label.configure(text="Ejected")

    def close_app(self, event=None):
        self.player.stop()
        self.destroy()
