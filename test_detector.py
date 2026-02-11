import time
import logging
import sys
from src.detector import CDDetector

# ログ設定
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def on_cd_event(action, path):
    print(f"EVENT DETECTED: {action.upper()} - {path}")

def main():
    print("Starting CD Detector Test... Press Ctrl+C to stop.")
    detector = CDDetector()
    detector.start_monitoring(on_cd_event)
    
    try:
        while True:
            detector.check()
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nStopping...")
        detector.stop_monitoring()

if __name__ == "__main__":
    main()

