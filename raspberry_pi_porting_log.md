# Raspberry Pi Porting Log

This document logs the steps taken to port the `cdp` macOS application to a Raspberry Pi (Linux) environment.

## 1. Initial Setup

*   **Git Branch:** A new branch named `feature/raspberry-pi-support` was created to isolate the porting work.
    ```bash
    git checkout -b feature/raspberry-pi-support
    ```
*   **Virtual Environment:** A Python virtual environment was created to manage project dependencies.
    ```bash
    python3 -m venv .venv
    ```

## 2. Dependency Management

1.  **Initial Installation Attempt:** The initial attempt to install dependencies from `requirements.txt` failed because the `pyobjc-framework-Cocoa` package is specific to macOS.

2.  **Modification of `requirements.txt`:** The `requirements.txt` file was modified to remove macOS-specific packages (`pyobjc-framework-Cocoa` and `python-vlc`).

3.  **Dependency Installation:** The modified list of dependencies was successfully installed into the virtual environment.
    ```bash
    .venv/bin/pip install -r requirements.txt
    ```
4.  **System-level Dependencies:** The following system packages were installed using `apt-get`:
    *   `vlc`: The media player backend.
    *   `libdiscid-dev`: The library required for reading disc IDs.
    ```bash
    sudo apt-get update && sudo apt-get install -y vlc libdiscid-dev
    ```

## 3. Code Modifications for Linux Compatibility

*   **`src/detector.py` (CD Detection):**
    *   The logic was changed from polling the macOS-specific `/Volumes` directory.
    *   It now polls for the existence of the `/dev/cdrom` device file, which is the standard for Linux.

*   **`src/player.py` (Playback Control):**
    *   The hardcoded path to the VLC application on macOS was changed to the standard `vlc` command.
    *   The playback method was updated to use the `cdda:///dev/cdrom` protocol for playing audio CDs on Linux.
    *   The disc eject command was changed from the macOS `drutil` to the Linux `eject` command.

*   **`src/fetcher.py` (Metadata Fetching):**
    *   The `get_disc_id` function was updated to accept a device path and use it with the `discid.read()` function, making it use the `/dev/cdrom` device detected by the detector.
