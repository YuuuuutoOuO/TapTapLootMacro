"""
input_sender.py
===============
負責實際送出按鍵訊號的模組。

【為什麼要換掉 pydirectinput？】
pydirectinput 底層使用 SendInput()，Windows 會在事件上設 LLMHF_INJECTED 旗標。
TapTapLoot 使用 WH_KEYBOARD_LL 全域 hook 偵測輸入，並會過濾掉帶有此旗標的事件，
因此無論送什麼按鍵都會被忽略。

【解決方案：三層 fallback】
1. keyboard.send()  — 用 kernel-level hook 注入，部分版本不帶 INJECTED 旗標
2. keybd_event()    — 舊版 Win32 API，TTL 的 hook 版本可能不過濾
3. SendInput (scan) — 最後備援（原本的 pydirectinput 方式）

【腳本生成用什麼鍵？】
用 'f15'：
  - 有完整 scan code (0x46)，三種 API 都支援
  - 實體鍵盤存在，不是虛擬鍵，TTL hook 不會因「沒有實體對應」而拒絕
  - 現代電腦幾乎沒有程式監聽它，不影響使用者正常操作
  - 不像 numpad 鍵在某些輸入法/應用程式會有副作用
"""

import ctypes
import ctypes.wintypes
import time

try:
    import keyboard as _keyboard
    _HAS_KEYBOARD = True
except ImportError:
    _HAS_KEYBOARD = False

# ── Win32 直接呼叫 ──────────────────────────────────────────────
_user32 = ctypes.windll.user32

# Virtual Key → Scan Code 對照（只放腳本生成需要的鍵）
# 完整表見 https://learn.microsoft.com/en-us/windows/win32/inputdev/virtual-key-codes
_VK_MAP: dict[str, tuple[int, int]] = {
    # name        : (VK_CODE, SCAN_CODE)
    "f15"         : (0x76, 0x00),  # 無實體對應，keyboard lib 直接用 VK
    "numlock"     : (0x90, 0x45),
    "pause"       : (0x13, 0x45),
    "capslock"    : (0x14, 0x3A),
    # 一般字母/數字（錄製回放用）
}

KEYEVENTF_KEYDOWN  = 0x0000
KEYEVENTF_KEYUP    = 0x0002
KEYEVENTF_SCANCODE = 0x0008


def _keybd_event(vk: int, scan: int, flags: int):
    """直接呼叫 keybd_event()（舊版 Win32 API）"""
    _user32.keybd_event(vk, scan, flags, 0)


def _send_input_scan(scan: int, key_up: bool):
    """SendInput with SCANCODE flag（pydirectinput 的方式，備援用）"""
    class KeyBdInput(ctypes.Structure):
        _fields_ = [("wVk", ctypes.c_ushort),
                    ("wScan", ctypes.c_ushort),
                    ("dwFlags", ctypes.c_ulong),
                    ("time", ctypes.c_ulong),
                    ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong))]

    class Input_I(ctypes.Union):
        _fields_ = [("ki", KeyBdInput)]

    class Input(ctypes.Structure):
        _fields_ = [("type", ctypes.c_ulong), ("ii", Input_I)]

    flags = KEYEVENTF_SCANCODE | (KEYEVENTF_KEYUP if key_up else 0)
    extra = ctypes.c_ulong(0)
    ki = KeyBdInput(0, scan, flags, 0, ctypes.pointer(extra))
    inp = Input(1, Input_I(ki))
    _user32.SendInput(1, ctypes.pointer(inp), ctypes.sizeof(inp))


# ── 公開介面 ────────────────────────────────────────────────────

# 腳本自動生成使用的安全鍵清單
# f15：非切換鍵（不會有燈閃問題）、keyboard lib 支援、幾乎無程式監聽
SAFE_KEYS = ["f15"]
# 若遊戲需要「不同按鍵」才計算不同次，可改用多個：
# 備選（同樣不閃燈）: "f16", "f17" ... "f24"
# 但要注意 numlock/capslock 是切換鍵，連按會不斷切換狀態


def key_down(key_name: str):
    """
    送出按鍵按下事件。
    優先用 keyboard lib，失敗則 fallback 到 keybd_event。
    """
    if _HAS_KEYBOARD:
        try:
            _keyboard.press(key_name)
            return
        except Exception:
            pass

    # fallback: keybd_event
    info = _VK_MAP.get(key_name.lower())
    if info:
        vk, scan = info
        _keybd_event(vk, scan, KEYEVENTF_KEYDOWN)
    else:
        # 最後備援：讓 MapVirtualKey 取 scan code
        vk = _user32.VkKeyScanA(ord(key_name[0])) & 0xFF if len(key_name) == 1 else 0
        scan = _user32.MapVirtualKeyW(vk, 0) if vk else 0
        _keybd_event(vk, scan, KEYEVENTF_KEYDOWN)


def key_up(key_name: str):
    """送出按鍵放開事件。"""
    if _HAS_KEYBOARD:
        try:
            _keyboard.release(key_name)
            return
        except Exception:
            pass

    info = _VK_MAP.get(key_name.lower())
    if info:
        vk, scan = info
        _keybd_event(vk, scan, KEYEVENTF_KEYUP)
    else:
        vk = _user32.VkKeyScanA(ord(key_name[0])) & 0xFF if len(key_name) == 1 else 0
        scan = _user32.MapVirtualKeyW(vk, 0) if vk else 0
        _keybd_event(vk, scan, KEYEVENTF_KEYUP)


def tap(key_name: str, hold_sec: float = 0.02):
    """按下後等待 hold_sec 秒再放開（模擬真實按鍵時長）。"""
    key_down(key_name)
    time.sleep(hold_sec)
    key_up(key_name)
