# Installation Guide

## Prerequisites

Before running `cdp`, ensure you have the following installed on your macOS system.

1.  **VLC Media Player**:
    Download and install VLC from [videolan.org](https://www.videolan.org/vlc/).
    Ensure it is located at `/Applications/VLC.app`.

2.  **Homebrew** (Package Manager):
    If not installed, follow instructions at [brew.sh](https://brew.sh/).

3.  **Python 3**:
    ```bash
    brew install python
    ```

4.  **libdiscid** (Required for DiscID calculation):
    ```bash
    brew install libdiscid
    ```

## Setup

1.  **Clone the repository** (if applicable) or navigate to the project directory.

2.  **Create a Virtual Environment**:
    It is recommended to use a virtual environment to manage dependencies.
    ```bash
    python3 -m venv .venv
    source .venv/bin/activate
    ```

3.  **Install Python Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *Note: If `requirements.txt` is missing, install the following manually:*
    ```bash
    pip install customtkinter musicbrainzngs python-vlc numpy pyobjc-framework-Cocoa discid requests pillow
    ```

## Configuration (Optional)

*   **CD & DVD Settings**:
    Go to **System Settings** -> **CDs & DVDs**.
    Set "When you insert a music CD" to **"Ignore"** (or "Do Nothing").
    This prevents the default Music.app from opening and conflicting with `cdp`.

## Running the Application

1.  Activate the virtual environment (if not already active):
    ```bash
    source .venv/bin/activate
    ```

2.  Run the main script:
    ```bash
    python main.py
    ```

3.  Insert a CD and enjoy!
    Press `Esc` or click the `×` button to exit.
