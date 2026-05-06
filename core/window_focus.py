"""
window_focus.py
===============
負責 Windows 視窗焦點偵測（GetForegroundWindow / SetForegroundWindow）。
"""

import ctypes
import time

_user32 = ctypes.windll.user32


def get_foreground() -> int:
    return _user32.GetForegroundWindow()


def set_foreground(hwnd: int):
    _user32.SetForegroundWindow(hwnd)
    time.sleep(0.05)   # 等待系統確認切換


def wait_and_lock_target(
    delay_seconds: int,
    own_hwnd: int,
    stop_event,
    status_cb,
    focus_enabled: bool,
) -> int | None:
    """
    倒數 delay_seconds 秒，等使用者切換到目標視窗後鎖定。
    - own_hwnd      : 本程式視窗 HWND（切走才算找到目標）
    - stop_event    : threading.Event，若 set 則中止
    - status_cb     : fn(msg, color) 更新 UI 狀態
    - focus_enabled : 是否啟用焦點偵測

    回傳鎖定的 target_hwnd，中止時回傳 None。
    """
    target_hwnd = None

    for d in range(delay_seconds, 0, -1):
        if stop_event.is_set():
            return None

        if target_hwnd:
            status_cb(f"🎯 已鎖定視窗，倒數 {d} 秒...", "orange")
        else:
            status_cb(f"⏳ 請切換至目標視窗... 倒數 {d} 秒", "orange")

        end_t = time.perf_counter() + 1.0
        while time.perf_counter() < end_t:
            if stop_event.is_set():
                return None

            if focus_enabled:
                curr = get_foreground()
                if target_hwnd is None:
                    if curr != own_hwnd and curr != 0:
                        target_hwnd = curr
                        status_cb(f"🎯 已鎖定！倒數 {d} 秒...", "orange")
                else:
                    if curr != target_hwnd:
                        stop_event.set()
                        status_cb("⚠️ 倒數期間切換視窗，已安全取消！", "red")
                        return None

            time.sleep(0.01)

    if target_hwnd is None:
        target_hwnd = get_foreground()

    # 確保焦點真正給目標視窗，讓輸入能被遊戲接收
    set_foreground(target_hwnd)
    return target_hwnd


def precise_sleep(
    duration: float,
    target_hwnd: int | None,
    stop_event,
    focus_enabled: bool,
    on_focus_lost,
):
    """
    精準等待 duration 秒，期間持續監控焦點與 stop_event。
    on_focus_lost : fn() 當偵測到焦點跑掉時呼叫
    """
    if duration <= 0:
        return

    end_time = time.perf_counter() + duration
    check = target_hwnd and focus_enabled

    while True:
        remaining = end_time - time.perf_counter()
        if remaining <= 0:
            break
        if stop_event.is_set():
            return
        if check and get_foreground() != target_hwnd:
            on_focus_lost()
            return
        time.sleep(min(0.01, remaining) if remaining > 0.015 else 0)
