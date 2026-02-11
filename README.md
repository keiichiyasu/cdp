# cdp - CD Auto-Player & Metadata Display

`cdp` is a Python-based CD player for macOS that automatically detects inserted audio CDs, fetches album metadata from MusicBrainz, and starts playback in a fullscreen interface optimized for HD TVs.

## Features

*   **Auto Detection**: Background monitoring of CD insertion/removal.
*   **Metadata Fetching**: Retrieves high-quality album art and track lists from MusicBrainz.
*   **TV-Optimized UI**: Ultra-large fonts and buttons designed for 1080p/720p screens.
*   **Robust Playback**: Uses VLC Media Player with `cdda://` protocol for stability.
*   **Multi-threaded Architecture**: No UI freezing during network or disc operations.
*   **Spectrum Visualizer (Optional)**: Real-time FFT-based frequency analysis.

## Requirements

*   **macOS**: 14.0 (Sonoma) or later.
*   **VLC Media Player**: Installed in `/Applications/VLC.app`.
*   **Python**: 3.10 or later.
*   **External Libraries**: `libdiscid` (via Homebrew: `brew install libdiscid`).

## Usage

Run the application:
```bash
python main.py [options]
```

### Options:
*   `--visualizer`: Enable the real-time FFT spectrum visualizer (experimental).
*   `--test`: Run in test mode with a 20Hz-20kHz swept-sine signal to verify audio/visual sync.

## Changelog

### v0.3.0 (2026-02-11)
*   **UI Redesign**: Scaled up all UI elements (2x) for better visibility on HD televisions.
*   **Metadata Robustness**: Added fallback search by album title if DiscID lookup fails.
*   **Bug Fixes**: Fixed `TclError` during rapid disc swapping and improved image reference handling.
*   **Visualizer**: Introduced optional FFT-based spectrum with rainbow gradient.

### v0.2.0
*   Implemented background threading for disc monitoring and metadata fetching.
*   Switched to `cdda://` and raw device access for stable playback.
*   Added focus management to maintain fullscreen mode.

## License
MIT
