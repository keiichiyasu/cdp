# cdp - CD Auto-Player & Metadata Display

`cdp` is a Python-based CD player for macOS that automatically detects inserted audio CDs, fetches album metadata from MusicBrainz, and starts playback in a fullscreen interface.

## Features

*   **Auto Detection**: Background monitoring of CD insertion.
*   **Metadata Fetching**: Retrieves album art, artist name, and track list from MusicBrainz.
*   **Fullscreen UI**: Always-on-top, immersive experience with large album art.
*   **Playback Control**: Play, Pause, Next, Previous, and Eject controls.
*   **Visualizer**: Smooth, procedural spectrum visualizer.
*   **Robust Playback**: Uses VLC Media Player with `cdda://` protocol and background processing.

## Requirements

*   **macOS**: 14.0 or later.
*   **VLC Media Player**: Installed in `/Applications/VLC.app`.
*   **Python**: 3.10 or later.
*   **External Libraries**: `libdiscid` (via Homebrew: `brew install libdiscid`).

## Quick Start

1.  Insert an Audio CD.
2.  Run: `python main.py`
3.  The app will auto-eject on startup, then wait for your CD.

## License
MIT
