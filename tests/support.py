"""テスト共通ヘルパ。"""
import time


def wait_until(predicate, timeout=5.0, interval=0.01):
    """predicate が真になるまで待つ。タイムアウトで False。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return True
        time.sleep(interval)
    return False
