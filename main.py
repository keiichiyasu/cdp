import logging
import sys
from src.ui import CDPApp

VERSION = "0.2.0"

def main():
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("cdp.md", mode='w', encoding='utf-8')
        ]
    )

    # ライブラリのログ抑制
    logging.getLogger("musicbrainzngs").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    
    app = CDPApp()
    app.mainloop()

if __name__ == "__main__":
    main()
