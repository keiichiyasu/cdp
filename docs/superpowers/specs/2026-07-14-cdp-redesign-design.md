# cdp 再設計 設計書(v0.4.0)

日付: 2026-07-14
ステータス: 承認済み(ブレインストーミングセッションにて全セクション承認)

## 1. 概要と目的

cdp を「Raspberry Pi を TV に常設する、操作不要の CD プレイヤー機」のアプリケーションとして再設計する。

再設計の 2 本柱:

1. **安定性・構造の刷新** — VLC サブプロセス制御の脆さ(状態が見えない・sleep 同期・自前トラックカウント)を構造ごと排除する
2. **UI/UX の刷新** — 「アートが主役」の眺めるための全画面 UI に作り直す

## 2. 決定事項(要件)

| 項目 | 決定 |
|---|---|
| ターゲット | Raspberry Pi 主軸。macOS は開発・テスト環境として動作維持 |
| 操作モデル | 基本操作不要。CD 挿入 → 自動再生、取り出し → 停止 |
| 音声出力 | HDMI(TV)。音量はアプリ側で制御しない(常に 100%、TV 側で調整) |
| 画面レイアウト | 案 A「アートが主役」: アルバムアートを大きく中央、曲名・アーティスト名は下に控えめ |
| アート未取得時 | 案 A「固定プレースホルダー」: 共通の CD アイコン画像 |
| ビジュアライザー | 廃止(FFT 解析・テストモード・sweep.wav も削除) |
| 再生バックエンド | VLC は使わない。自前 PCM パイプライン(cdparanoia + sounddevice) |
| スコープ | アプリ本体のみ。OS キオスク化(自動起動等)は含めない |

## 3. 現状の問題(再設計で解消するもの)

- VLC を rc インターフェイス(stdin 文字列)で制御しており、再生状態・トラック番号が取得できず Python 側で推測している。`time.sleep(5.0)` 等の時間待ちで同期している
- Raspberry Pi 対応がコミット `c4ebf92` で退行し、player.py が macOS 専用実装(VLC.app ハードコード、drutil)に戻っている
- Linux のディスク検知が `/dev/cdrom` の存在チェックであり、メディアの有無を判定できていない
- ビジュアライザーの再生位置同期が擬似的(経過時間からの推定)でズレる
- UI クラス(CDPApp)が検知・取得・再生・描画のすべてを抱えている。bare except が多数
- メタデータ取得の完了を待ってから再生を開始するため、挿入から発音までが遅い

## 4. アーキテクチャ

3 層構造。プラットフォーム差は「検知」と「トラック供給」の 2 点のみに閉じ込める。

```
[プラットフォーム層]                [コア層(OS 非依存)]            [表示層]
DiscMonitor ──イベント──▶ AppController(状態機械) ──状態──▶ View(Tkinter)
TrackSource ──PCM──▶ PlaybackEngine ─┘   ▲
                                          │
                     TocReader / MetadataService(ワーカー)
```

- **AppController** が唯一の調停役。各スレッド(検知・再生・取得)からのイベントをスレッドセーフなキューで受け、状態遷移を決定し、View には状態スナップショットのみを渡す(View は Tk メインループ上で描画)
- **再生とメタデータは完全に独立**。TOC 読取後ただちに再生を開始し、メタデータ・アートワーク取得は並行して走る。メタデータ系の失敗は表示にのみ影響し、再生には影響しない

### 状態機械

```
NO_DISC ──挿入検知──▶ READING(トラック列挙) ──▶ PLAYING ──取り出し──▶ NO_DISC
                          │                        │
                          └──読取不能──▶ ERROR ────┘(取り出しで NO_DISC へ)
```

- どの状態でも取り出しイベントで即 NO_DISC へ戻る
- PLAYING 中はトラック終端で自動的に次トラックへ。最終トラック終了後は FINISHED 状態(先頭には戻らない。ディスクは入ったまま)。FINISHED の画面は再生中画面を流用し、トラック表示部を「再生終了」にする。取り出しで NO_DISC へ

### ディレクトリ構成

```
main.py               # エントリポイント、組み立て(DI)
assets/placeholder.png
src/
  core/
    controller.py     # AppController(状態機械)
    events.py         # イベント・状態 dataclass 定義
  disc/
    monitor.py        # DiscMonitor(OS 別バックエンド)
    toc.py            # TocReader(discid)
  audio/
    engine.py         # PlaybackEngine
    sources.py        # TrackSource(OS 別バックエンド)
  metadata/
    fetcher.py        # MusicBrainz + Cover Art Archive
    cache.py          # ディスク単位のローカルキャッシュ
  ui/
    view.py           # 全画面 View(レイアウト A)
tests/                # pytest
```

## 5. コンポーネント仕様

### DiscMonitor(検知)

- 専用スレッドで 2 秒間隔ポーリング。イベント: `disc_inserted` / `disc_removed`
- **Linux**: `/dev/sr0`(設定で変更可)を `O_NONBLOCK` で開き `ioctl(CDROM_DRIVE_STATUS)` でメディア有無を判定。`CDROM_DISC_STATUS` でオーディオ CD(CDS_AUDIO / CDS_MIXED)かを確認し、データディスクは `not_audio_cd` イベントとして区別する
- **macOS**: /Volumes ポーリング。新規ボリューム直下に .aiff が存在すればオーディオ CD と判定

### TocReader

- discid で DiscID・トラック数・各トラック長を読む。3 回リトライ(バックオフ付き)
- Linux は `/dev/sr0`、macOS はマウントパスから raw デバイスを解決(現行ロジックを整理して継承)
- 出力: `DiscInfo(disc_id, tracks: list[TrackRef(number, duration)])`
- **DiscID が読めなくても再生は妨げない**。トラック列挙のフォールバック: Linux は `cdparanoia -Q` の出力、macOS は .aiff ファイル一覧

### PlaybackEngine(再生)

- 専用スレッド。TrackSource から PCM チャンクを読み、先読みリングバッファ(5〜10 秒分)を挟んで `sounddevice.RawOutputStream`(44.1kHz / 16bit / 2ch)へ書き続ける
- 再生位置 = 書き込んだフレーム数 ÷ 44100。トラック番号もエンジンが所有(推測が発生しない)
- 操作: `pause()` / `resume()` / `stop()` / `next()` / `prev()`。トラック切替はソースを開き直すだけ。`prev()` は前トラックへ(トラック 1 では曲頭へ戻る)
- トラック終端で自動的に次トラックへ。読み取りが停止した場合(傷ディスク)は無音を出力して待ち、10 秒でそのトラックをスキップして警告イベントを発行
- 位置・トラックの変化はイベントとしてコントローラへ通知

### TrackSource(トラック供給)

- インターフェイス: `open(track_no)` → PCM チャンクのイテレータ、`close()`
- **Linux — CdparanoiaSource**: `cdparanoia -q -r -Z -d <device> <track_no> -` を子プロセス起動し stdout から raw PCM(44.1k/16bit/2ch/LE)を読む(`-r` = リトルエンディアン raw 出力)。トラック切替 = プロセス terminate + 再起動
  - `-Z`(paranoia 検証の無効化)は再生用途のための判断。実機計測(Raspberry Pi 4 + USB ドライブ)では、有効時の発音開始が 2.9〜7.0 秒とばらつくのに対し `-Z` では 1.3 秒で安定した。また傷ディスクでは、有効だとリトライが長引いて stall 検知(10 秒)に達しトラックごとスキップされるが、無効ならドライブ自身の誤り訂正に任せて再生を継続できる。多重読み・照合はアーカイブ用途の機能であり、リアルタイム再生では不要
- **macOS — AiffFileSource**: マウントされた .aiff を soundfile で読み PCM を返す

### MetadataService

- キャッシュ: `~/.cache/cdp/<disc_id>/metadata.json` + `cover.jpg`。ヒット時はネット不要(再挿入時オフライン動作)
- ミス時: MusicBrainz DiscID 検索 → 失敗時はタイトル検索フォールバック(タイトルは macOS のボリューム名のみ。Linux ではタイトル情報がないためフォールバックなし)→ Cover Art Archive(front)
- タイムアウト・リトライは有限。ワーカースレッドで実行し、結果(`metadata_ready` / `artwork_ready` / `metadata_failed`)をイベントで返す
- DiscID が無い場合はキャッシュも検索も行わない(トラック番号表示のみ)

### View(表示)

- 素の Tkinter + Pillow(CustomTkinter は依存から削除)。全画面・カーソル非表示・黒背景
- 画面状態は 4 つ:
  1. **待機**(NO_DISC): 暗い画面に小さく CD アイコン
  2. **読込中**(READING): 控えめな「読み込み中...」表示
  3. **再生中**(PLAYING): アルバムアートを画面高さの約 70% で中央表示。下部に「トラック番号. 曲名」「アーティスト名」を控えめに、「N / 総トラック数」を併記。アート未取得時は固定プレースホルダー画像
  4. **エラー**(ERROR): 短い日本語メッセージ(例: 「このディスクは再生できません」)
- フォントサイズは画面高さから算出(720p/1080p 両対応)
- 開発用の隠しキー操作(画面には表示しない): Space = 一時停止/再開、n/p = 曲送り/戻し、e = イジェクト(Linux: `eject` コマンド、macOS: `drutil eject`)、Esc = 終了

## 6. エラー処理方針

- bare except は全廃。コンポーネント境界で例外を捕捉し、型付きイベント(`playback_error` 等)としてコントローラへ渡す
- 主なエッジケース:
  - データ CD / DVD → 「オーディオ CD ではありません」表示、再生しない
  - 再生中のドライブボタンによる取り出し → 検知イベントで即停止、待機画面へ
  - 音声デバイス初期化失敗(HDMI 未接続等)→ エラー表示し、30 秒間隔でリトライ
  - ネットワーク不通 → キャッシュ → プレースホルダー。再生には無影響
- ログ: logging を使用し、RotatingFileHandler(cdp.log、上限あり)+標準出力

## 7. テスト戦略

- pytest を導入。`tests/` 配下
- **コア層はハードウェアなしで全遷移をテスト**: FakeDiscMonitor / FakeTrackSource / モック化した MetadataService を注入し、挿入→即再生、再生中の取り出し、メタデータの遅延到着、傷ディスクのスキップ、データ CD 拒否などを検証
- PlaybackEngine: 生成 PCM を返す FakeTrackSource で pause / next / トラック終端自動送り / アンダーラン時のスキップを検証(sounddevice はモック)
- MetadataService: キャッシュヒット/ミス、API はモック
- 実機スモーク: macOS(.aiff)で開発中随時。Raspberry Pi は受け入れチェックリスト(README に記載)で確認

## 8. 依存関係

| 種別 | 追加 | 継続 | 削除 |
|---|---|---|---|
| Python(pip) | sounddevice, soundfile | discid, musicbrainzngs, requests, pillow | customtkinter, numpy |
| システム(RPi/apt) | cdparanoia, libportaudio2 | libdiscid0 | vlc |
| システム(mac/brew) | portaudio | libdiscid | VLC.app |
| リポジトリ内 | assets/placeholder.png | — | sweep.wav, cdp.md(実体はログ) |

## 9. 移行計画

1. 現在の未コミット変更(src/ui.py の TclError 対策)を「v0.3.x 最終」としてコミットし、基線を残す
2. 再設計ブランチを切り、新構成を実装(旧 player.py / visualizer / テストモードは削除)
3. design_spec.md は本設計書への参照に置換。README / INSTALL.md / requirements.txt を RPi 主軸で書き直す
4. バージョンは 0.4.0

## 10. スコープ外

- OS キオスク化(systemd 自動起動、画面ブランク無効化、セットアップスクリプト)— 将来の別プロジェクト
- リモコン・スマホ操作、リッピング、ライブラリ管理などの機能拡張
- ビジュアライザー(廃止。ただし本設計では PCM をアプリが所有するため、将来再実装する場合の技術的障壁は低い)
