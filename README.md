# cdp - CD Auto-Player & Metadata Display

`cdp` is a Python-based CD player that automatically detects inserted audio CDs, fetches album metadata from MusicBrainz, and starts playback in a fullscreen interface. It supports both macOS and Raspberry Pi/Linux platforms.

![CDP Screenshot](https://via.placeholder.com/800x450?text=CDP+Interface)

## Features

*   **Auto Detection**: Automatically detects when an Audio CD is inserted.
*   **Metadata Fetching**: Retrieves album art, artist name, and track list from MusicBrainz using `libdiscid`.
*   **Fullscreen UI**: Provides an immersive, fullscreen experience with large album art.
*   **Playback Control**: Play, Pause, Next, Previous, and Eject controls.
*   **Visualizer**: Simple spectrum visualizer (placeholder).
*   **Robust Playback**: Uses VLC Media Player as a backend for reliable audio playback.

## Requirements

*   **Operating System**:
    *   **macOS**: Tested on macOS (Darwin). VLC Media Player must be installed in `/Applications/VLC.app`. `libdiscid` installed via Homebrew.
    *   **Raspberry Pi OS / Linux**: Tested on Raspberry Pi OS. VLC Media Player must be installed and accessible in the system's PATH. `libdiscid` installed via package manager (e.g., `sudo apt-get install libdiscid-dev vlc`).
*   **Python**: 3.10 or later.

## Quick Start

1.  Insert an Audio CD.
2.  Run the application:
    ```bash
    python main.py
    ```
3.  The application will detect the CD, load metadata, and start playing.

## Architecture

*   `src/detector.py`: Monitors `/Volumes` for CD mounts.
*   `src/fetcher.py`: Handles MusicBrainz API interactions.
*   `src/player.py`: Controls the external VLC process via RC interface.
*   `src/ui.py`: CustomTkinter-based GUI.

## License

MIT License
