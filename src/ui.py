import customtkinter as ctk
import logging
from PIL import Image, ImageTk, ImageFilter
import requests
from io import BytesIO
import random # ビジュアライザー用ダミーデータ

from src.detector import CDDetector
from src.fetcher import MetadataFetcher
from src.player import CDPlayer

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("dark-blue")

class TextHandler(logging.Handler):
    def __init__(self, text_widget):
        super().__init__()
        self.text_widget = text_widget

    def emit(self, record):
        msg = self.format(record)
        def append():
            try:
                self.text_widget.configure(state="normal")
                self.text_widget.insert("end", msg + "\n")
                self.text_widget.see("end")
                self.text_widget.configure(state="disabled")
            except:
                pass
        try:
            self.text_widget.after(0, append)
        except:
            pass

class CDPApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("CDP - CD Player")
        self.geometry("800x600")
        self.attributes("-fullscreen", True)
        
        # 終了ショートカット
        self.bind("<Escape>", self.close_app)
        
        # モジュール初期化
        self.player = CDPlayer()
        self.fetcher = MetadataFetcher()
        self.detector = CDDetector() 
        
        # UI構築
        self._setup_ui()

        # ログ設定
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.INFO)
        
        # GUIログハンドラ
        text_handler = TextHandler(self.log_textbox)
        text_handler.setFormatter(logging.Formatter('%(asctime)s: %(message)s'))
        self.logger.addHandler(text_handler)
        
        self.logger.info("Application starting...")

        # CD検知開始
        self.detector.start_monitoring(self._on_cd_event)
        self.after(1000, self._poll_detector)

        # 定期更新ループ開始
        self.after(100, self._update_loop)

    def _setup_ui(self):
        # グリッド構成
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1) # Main Content
        self.grid_rowconfigure(1, weight=0) # Controls

        # 背景兼メインコンテナ
        self.main_frame = ctk.CTkFrame(self, fg_color="black")
        self.main_frame.grid(row=0, column=0, sticky="nsew", padx=0, pady=0)
        self.main_frame.grid_columnconfigure(0, weight=1)
        self.main_frame.grid_rowconfigure(0, weight=1) # Artwork
        self.main_frame.grid_rowconfigure(1, weight=0) # Visualizer

        # アルバムアート
        self.art_label = ctk.CTkLabel(self.main_frame, text="", text_color="gray")
        self.art_label.grid(row=0, column=0, sticky="nsew")
        
        # デバッグログ表示用オーバーレイ
        self.log_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        self.log_frame.grid(row=0, column=0, sticky="ne", padx=10, pady=10)
        
        # 終了ボタン
        self.btn_close = ctk.CTkButton(self.log_frame, text="×", width=30, height=30, fg_color="red", command=self.close_app)
        self.btn_close.pack(side="right", anchor="ne")
        
        self.log_textbox = ctk.CTkTextbox(self.log_frame, width=400, height=200, fg_color="black", text_color="green", font=("Courier", 10))
        self.log_textbox.pack(side="right", padx=(0, 10))
        self.log_textbox.insert("0.0", "--- Log Started ---\n")
        self.log_textbox.configure(state="disabled")

        # ビジュアライザー (Canvas)
        self.spectrum_canvas = ctk.CTkCanvas(self.main_frame, height=100, bg="black", highlightthickness=0)
        self.spectrum_canvas.grid(row=1, column=0, sticky="ew", padx=20, pady=(0, 20))

        # コントロールパネル
        self.controls_frame = ctk.CTkFrame(self, height=100, fg_color="#111111")
        self.controls_frame.grid(row=1, column=0, sticky="ew")
        self.controls_frame.grid_columnconfigure((0,1,2,3,4), weight=1)

        # ボタン
        self.btn_eject = ctk.CTkButton(self.controls_frame, text="⏏", width=50, fg_color="#555555", hover_color="#777777", command=self._eject)
        self.btn_eject.grid(row=0, column=0, pady=20, padx=(20, 0))

        self.btn_prev = ctk.CTkButton(self.controls_frame, text="⏮", width=50, command=self.player.prev_track)
        self.btn_prev.grid(row=0, column=1, pady=20)

        self.btn_play = ctk.CTkButton(self.controls_frame, text="⏯", width=60, command=self._toggle_play)
        self.btn_play.grid(row=0, column=2, pady=20)

        self.btn_next = ctk.CTkButton(self.controls_frame, text="⏭", width=50, command=self.player.next_track)
        self.btn_next.grid(row=0, column=3, pady=20)

        # 情報ラベル
        self.info_label = ctk.CTkLabel(self.controls_frame, text="No Disc", font=("Helvetica", 16))
        self.info_label.grid(row=1, column=0, columnspan=5, pady=(0, 10))

        # デフォルト画像のロード
        self.current_image = None
        self._update_album_art(None)

    def _eject(self):
        self.player.eject_disc()
        self.info_label.configure(text="No Disc")
        self.art_label.configure(image=None, text="Waiting for CD...")
    
    def _toggle_play(self):
        if self.player.is_playing():
            self.player.pause()
        else:
            self.player.play()

    def _update_album_art(self, image_url):
        # 実際にはURLから画像をダウンロードして表示
        if image_url:
            try:
                response = requests.get(image_url)
                img_data = BytesIO(response.content)
                pil_image = Image.open(img_data)
                
                # 画面サイズに合わせてリサイズ
                screen_h = self.winfo_screenheight()
                target_h = int(screen_h * 0.6)
                ratio = target_h / pil_image.height
                target_w = int(pil_image.width * ratio)
                
                pil_image = pil_image.resize((target_w, target_h), Image.Resampling.LANCZOS)
                self.current_image = ctk.CTkImage(light_image=pil_image, dark_image=pil_image, size=(target_w, target_h))
                self.art_label.configure(image=self.current_image, text="")
            except Exception as e:
                self.logger.error(f"Failed to load image: {e}")
                self.art_label.configure(image=None, text="Image Load Error")
        else:
            self.art_label.configure(image=None, text="Waiting for CD...")

    def _poll_detector(self):
        """定期的にDetectorをチェック"""
        self.detector.check()
        self.after(1000, self._poll_detector)

    def _on_cd_event(self, action, path):
        self.logger.info(f"UI Event: {action} - {path}")
        if action == "mount":
            self.after(2000, lambda: self._handle_disc_insertion(path))
        elif action == "unmount":
            # 再生中（VLC起動中）のアンマウントは意図的なので無視
            if self.player.is_playing():
                self.logger.info("Ignored unmount event during playback.")
                return
                
            self.info_label.configure(text="No Disc")
            self.art_label.configure(image=None, text="Waiting for CD...")
            if self.player.is_playing():
                self.player.stop()

    def _handle_disc_insertion(self, path):
        # 1. メタデータ取得
        disc_id = self.fetcher.get_disc_id(path)
        metadata = self.fetcher.fetch_metadata(disc_id)
        
        if metadata:
            self.logger.info(f"Metadata found: {metadata['title']}")
            self.info_label.configure(text=f"{metadata['title']} - {metadata['artist']}")
            self._update_album_art(metadata['cover_art_url'])
        else:
            self.info_label.configure(text="Unknown Album")
        
        # 2. 再生開始
        self.player.play_cd(drive_path=path)

    def _update_loop(self):
        # ビジュアライザーの更新
        self.spectrum_canvas.delete("all")
        w = self.spectrum_canvas.winfo_width()
        h = self.spectrum_canvas.winfo_height()
        
        bar_count = 50
        bar_width = w / bar_count
        
        if self.player.is_playing():
            for i in range(bar_count):
                val = random.random() * h
                x0 = i * bar_width
                y0 = h - val
                x1 = x0 + bar_width - 2
                y1 = h
                
                self.spectrum_canvas.create_rectangle(x0, y0, x1, y1, fill="#00ff00", outline="")
        
        self.after(50, self._update_loop)

    def close_app(self, event=None):
        self.player.stop()
        self.destroy()