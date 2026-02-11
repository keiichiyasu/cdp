import customtkinter as ctk
import logging
from PIL import Image, ImageTk
import requests
from io import BytesIO
import random
import traceback
import threading
import time
import colorsys
import os

from src.detector import get_detector
from src.fetcher import MetadataFetcher
from src.player import CDPlayer

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class CDPApp(ctk.CTk):
    def __init__(self, test_mode=False, show_visualizer=False):
        super().__init__()

        self.title("CDP - CD Player")
        self.attributes("-fullscreen", True)
        self.attributes("-topmost", True)
        self.bind("<Escape>", self.close_app)
        
        self.player = CDPlayer(test_mode=test_mode)
        self.fetcher = MetadataFetcher()
        self.detector = get_detector()
        self.current_metadata = None
        self.show_visualizer = show_visualizer
        
        self._setup_ui()
        self.logger = logging.getLogger("CDP")

        self._bar_ids = []
        self._current_heights = [0.0] * 256
        self._decay_rate = 0.88
        
        self.after(500, self.player.eject_disc)
        threading.Thread(target=self._detector_thread, daemon=True).start()
        self.after(100, self._update_loop)

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) # Main Area
        self.grid_rowconfigure(1, weight=0) # Controls

        # メインエリア（アルバムアート & ビジュアライザー）
        self.main_frame = ctk.CTkFrame(self, fg_color="black")
        self.main_frame.grid(row=0, column=0, sticky="nsew")
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1)

        # アルバムアート/ステータスラベル (フォールバックフォントサイズ拡大)
        self.art_label = ctk.CTkLabel(self.main_frame, text="Waiting for CD...", text_color="gray", font=("Helvetica", 48, "bold"))
        self.art_label.grid(row=0, column=0, sticky="nsew")
        
        if self.show_visualizer:
            self.spectrum_canvas = ctk.CTkCanvas(self.main_frame, height=300, bg="black", highlightthickness=0)
            self.spectrum_canvas.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 40))
        else:
            self.spectrum_canvas = None

        # コントロールパネル (高さ拡大)
        self.controls_frame = ctk.CTkFrame(self, height=220, fg_color="#111111")
        self.controls_frame.grid(row=1, column=0, sticky="ew")
        self.controls_frame.grid_columnconfigure((0,1,2,3,4), weight=1)
        
        # 特大ボタン
        btn_font = ("Helvetica", 32)
        ctk.CTkButton(self.controls_frame, text="⏏", width=120, height=80, font=btn_font, command=self._eject).grid(row=0, column=0, pady=20)
        ctk.CTkButton(self.controls_frame, text="⏮", width=120, height=80, font=btn_font, command=self.player.prev_track).grid(row=0, column=1)
        ctk.CTkButton(self.controls_frame, text="⏯", width=180, height=80, font=btn_font, command=self._toggle_play).grid(row=0, column=2)
        ctk.CTkButton(self.controls_frame, text="⏭", width=120, height=80, font=btn_font, command=self.player.next_track).grid(row=0, column=3)
        
        # 情報ラベル (フォントサイズ特大)
        self.info_label = ctk.CTkLabel(self.controls_frame, text="Ready", font=("Helvetica", 36, "bold"))
        self.info_label.grid(row=1, column=0, columnspan=5, pady=(0, 20))

    def _init_bars(self, width, height):
        bar_count = 256
        bar_width = width / bar_count
        for i in range(bar_count):
            hue = (i / bar_count) * 0.8
            rgb = colorsys.hsv_to_rgb(hue, 0.9, 1.0)
            hex_color = '#%02x%02x%02x' % (int(rgb[0]*255), int(rgb[1]*255), int(rgb[2]*255))
            rect_id = self.spectrum_canvas.create_rectangle(
                i * bar_width, height, (i + 1) * bar_width - 1, height,
                fill=hex_color, outline=""
            )
            self._bar_ids.append(rect_id)

    def _update_loop(self):
        if self.show_visualizer and self.spectrum_canvas:
            w = self.spectrum_canvas.winfo_width()
            h = self.spectrum_canvas.winfo_height()
            if w > 1 and not self._bar_ids: self._init_bars(w, h)
            if self.player.is_playing() and self._bar_ids:
                spectrum = self.player.get_spectrum()
                bw = w / 256
                for i, target_val in enumerate(spectrum):
                    current_h = self._current_heights[i]
                    new_h = max(current_h * self._decay_rate, target_val * h)
                    self._current_heights[i] = new_h
                    self.spectrum_canvas.coords(self._bar_ids[i], i*bw, h - new_h, (i+1)*bw-1, h)
        
        if self.player.is_playing():
            if not hasattr(self, '_up_cnt'): self._up_cnt = 0
            self._up_cnt += 1
            if self._up_cnt > 30:
                self._up_cnt = 0
                if self.current_metadata and self.current_metadata['tracks']:
                    idx = self.player.get_track_index() - 1
                    if 0 <= idx < len(self.current_metadata['tracks']):
                        t = self.current_metadata['tracks'][idx]
                        self.info_label.configure(text=f"{t['number']}. {t['title']} - {self.current_metadata['artist']}")

        self.after(25, self._update_loop)

    def _detector_thread(self):
        self.detector.start_monitoring(self._queue_cd_event)
        while True:
            try: self.detector.check()
            except: pass
            time.sleep(1)

    def _queue_cd_event(self, action, path):
        self.after(0, lambda: self._on_cd_event(action, path))

    def _on_cd_event(self, action, path):
        if action == "mount": self.after(2000, lambda: self._handle_disc_insertion(path))
        elif action == "unmount":
            self.info_label.configure(text="No Disc")
            self.art_label.configure(image=None, text="Waiting for CD...", font=("Helvetica", 48, "bold"))
            self.current_metadata = None

    def _handle_disc_insertion(self, path):
        self.info_label.configure(text="💿 Loading Metadata...")
        def task():
            try:
                vol_name = os.path.basename(path)
                disc_id = self.fetcher.get_disc_id(path)
                metadata = self.fetcher.fetch_metadata(disc_id, fallback_title=vol_name)
                
                def update_text():
                    self.current_metadata = metadata
                    if metadata:
                        title = metadata['tracks'][0]['title'] if metadata['tracks'] else metadata['title']
                        self.info_label.configure(text=f"1. {title} - {metadata['artist']}")
                    else:
                        self.info_label.configure(text="Unknown Album (Metadata not found)")
                self.after(0, update_text)

                self.player.play_cd(drive_path=path)
                self.after(1000, self.focus_force)

                if metadata and metadata.get('cover_art_url'):
                    try:
                        self.logger.info(f"Downloading artwork: {metadata['cover_art_url']}")
                        headers = {'User-Agent': 'CDP/0.2 (contact@example.com)'}
                        resp = requests.get(metadata['cover_art_url'], headers=headers, timeout=15)
                        resp.raise_for_status()
                        pil_img = Image.open(BytesIO(resp.content))
                        pil_img.load()
                        self.after(0, lambda: self._show_image(pil_img))
                    except Exception as e:
                        self.logger.warning(f"Artwork download failed: {e}")
                        # 画像取得失敗時は、確実に image=None をセットする
                        self.after(0, lambda: self.art_label.configure(image=None, text="No Artwork Available", font=("Helvetica", 48, "bold")))
            except Exception as e:
                self.logger.error(f"Error in insertion task: {e}")
                self.after(0, lambda: self.info_label.configure(text=f"Error: {str(e)}"))
        threading.Thread(target=task, daemon=True).start()

    def _show_image(self, pil_img):
        try:
            self.art_label.configure(image=None)
            screen_h = self.winfo_screenheight()
            # TV向けに画像も少し大きく (画面高の70%)
            target_h = int(screen_h * 0.7)
            ratio = target_h / pil_img.height
            target_w = int(pil_img.width * ratio)
            pil_resized = pil_img.resize((target_w, target_h), Image.Resampling.LANCZOS)
            self.current_image = ctk.CTkImage(light_image=pil_resized, dark_image=pil_resized, size=(target_w, target_h))
            self.art_label.configure(image=self.current_image, text="")
        except: pass

    def _toggle_play(self):
        if self.player.is_playing(): self.player.pause()
        else: self.player.play()

    def _eject(self):
        self.player.eject_disc()
        self.info_label.configure(text="Ejected")
        # アートワークをクリア
        self.art_label.configure(image=None, text="Waiting for CD...", font=("Helvetica", 48, "bold"))
        self.current_metadata = None

    def close_app(self, event=None):
        self.player.stop()
        self.destroy()
