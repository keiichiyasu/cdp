import logging
import sys
import argparse
from src.ui import CDPApp

VERSION = "0.3.0"

def main():
    parser = argparse.ArgumentParser(description="CDP - CD Auto-Player")
    parser.add_argument("--test", action="store_true", help="Run in test mode with sweep signal")
    parser.add_argument("--visualizer", action="store_true", help="Enable spectrum visualizer")
    args = parser.parse_args()

    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("cdp.log", mode='w', encoding='utf-8')
        ]
    )

    # ライブラリのログ抑制
    logging.getLogger("musicbrainzngs").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    app = CDPApp(test_mode=args.test, show_visualizer=args.visualizer)
    app.mainloop()

if __name__ == "__main__":
    main()
