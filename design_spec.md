# cdp - CD Auto-Player & Metadata Display System 設計書

## 1. プロジェクト概要
物理CD（音楽CD）がPC（macOS）に挿入されたことを検知し、自動的にインターネット上のデータベースからアルバムアートやトラック情報を取得して全画面で表示すると同時に、楽曲の再生を開始するデスクトップアプリケーション。

... (中略) ...

## 6. ディレクトリ構造イメージ

```
cdp/
├── main.py            # エントリーポイント
├── requirements.txt   # 依存ライブラリ
├── assets/            # デフォルト画像、アイコンなど
├── src/
│   ├── __init__.py
│   ├── detector.py    # CD検知ロジック (macOS用)
│   ├── fetcher.py     # API通信 (MusicBrainz)
│   ├── player.py      # 音声再生・FFT解析
│   └── ui.py          # GUI (CustomTkinter) & ビジュアライザー
└── design_spec.md     # 本設計書
```

## 7. 今後のステップ
1.  環境構築（必要なライブラリのインストール）
2.  `detector.py` の実装（macOSでのCD認識テスト）
3.  `fetcher.py` の実装（MusicBrainzとの通信テスト）
4.  `player.py` の実装（VLCでのCD再生テスト）
5.  `ui.py` の実装と各モジュールの結合
