# インストール手順

## Raspberry Pi (Raspberry Pi OS)

```bash
sudo apt-get update
sudo apt-get install -y cdparanoia libdiscid0 libportaudio2 python3-tk python3-venv

git clone https://github.com/keiichiyasu/cdp.git
cd cdp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
.venv/bin/python main.py
```

- 音声は HDMI から出ます。出ない場合は `sudo raspi-config` → System Options → Audio で HDMI を選択してください。
- CD ドライブは `/dev/sr0` を想定しています(USB 接続の光学ドライブで確認)。
- Pillow の ImageTk 読み込みでエラーが出る場合: `sudo apt-get install -y python3-pil.imagetk`

## macOS(開発用)

```bash
brew install libdiscid python-tk@3.14

git clone https://github.com/keiichiyasu/cdp.git
cd cdp
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt -r requirements-dev.txt
.venv/bin/python main.py
```

- `python-tk@3.14` は Tkinter 用です。Homebrew の Python には既定で含まれないため別途必要です
  (バージョン番号は使用する Python に合わせてください)。
- PortAudio / libsndfile は pip の wheel に同梱されるため brew 不要です。
- テスト実行: `.venv/bin/python -m pytest`
