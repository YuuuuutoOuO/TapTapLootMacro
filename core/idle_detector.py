"""
idle_detector.py
================
掛機偵測：使用者超過 N 分鐘沒動作，自動開始輸出 f15。
使用者一動就立刻停止。
"""

import threading
import time

from .input_sender import SAFE_KEYS, tap


class IdleDetector:
    def __init__(self, status_cb):
        self._status_cb = status_cb
        self._last_activity = time.monotonic()
        self._active = False          # 是否正在輸出
        self._stop_evt = threading.Event()
        self._enabled = False
        self._threshold_sec = 300.0   # 預設 5 分鐘

        self._watcher = threading.Thread(target=self._watch_loop, daemon=True)
        self._watcher.start()

    # ── 設定 ────────────────────────────────────────────────────
    def set_enabled(self, enabled: bool):
        self._enabled = enabled

    def set_threshold_minutes(self, minutes: float):
        self._threshold_sec = max(0.1, minutes) * 60

    # ── 活動通知（由 UI 呼叫）───────────────────────────────────
    def notify_activity(self):
        self._last_activity = time.monotonic()
        if self._active:
            self._active = False
            self._stop_evt.set()
            self._status_cb("準備就緒（掛機偵測：使用者已回來）", "blue")

    # ── 背景監控 ─────────────────────────────────────────────────
    def _watch_loop(self):
        while True:
            time.sleep(3)
            if not self._enabled or self._active:
                continue
            if time.monotonic() - self._last_activity >= self._threshold_sec:
                self._active = True
                self._stop_evt.clear()
                threading.Thread(target=self._output_loop, daemon=True).start()

    def _output_loop(self):
        self._status_cb(f"💤 掛機偵測：自動輸出中 ({SAFE_KEYS[0]})...", "purple")
        interval = 0.05   # 約 20 CPS
        while self._active:
            tap(SAFE_KEYS[0])
            self._stop_evt.wait(timeout=interval)
