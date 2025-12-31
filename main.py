import logging
import sys
from src.ui import CDPApp

def main():
    # ログ設定
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("cdp.log", mode='w', encoding='utf-8')
        ]
    )
    
    app = CDPApp()
    app.mainloop()

if __name__ == "__main__":
    main()
