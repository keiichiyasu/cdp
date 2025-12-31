import time
import logging
from src.detector import CDDetector
from PyObjCTools import AppHelper

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def on_cd_event(action, path):
    print(f"EVENT DETECTED: {action.upper()} - {path}")

def main():
    print("Starting CD Detector Test... Press Ctrl+C to stop.")
    detector = CDDetector.alloc().init()
    detector.start_monitoring(on_cd_event)
    
    try:
        # コンソールアプリとしてRunLoopを開始
        AppHelper.runConsoleEventLoop()
    except KeyboardInterrupt:
        print("\nStopping...")
        detector.stop_monitoring()

if __name__ == "__main__":
    main()

