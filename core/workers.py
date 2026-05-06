"""
workers.py
==========
錄製、回放、自動生成腳本的工作函式（在背景執行緒中執行）。
每個函式都是純邏輯，不直接操作 tkinter UI（透過 callback 通知）。
"""

import json
import os
import random
import time

import keyboard

from .input_sender import SAFE_KEYS, key_down, key_up
from .window_focus import get_foreground, wait_and_lock_target, precise_sleep


# ── 生成腳本 ────────────────────────────────────────────────────

def generate_work(cps, output_file, stop_event, status_cb, done_cb):
    """
    自動生成連點腳本並儲存為 JSON。

    使用 SAFE_KEYS（預設 scrolllock）：
      - scrolllock 有完整 scan code (0x46)、實體鍵存在
      - keyboard lib 透過 hook 注入，繞過 LLMHF_INJECTED 問題
      - TapTapLoot WH_KEYBOARD_LL hook 能正確收到
      - 對使用者幾乎無副作用
    """
    try:
        status_cb(f"⚙️ 正在生成腳本 ({cps} 下/秒)...", "blue")

        raw_intervals = [random.uniform(0.5, 1.5) for _ in range(cps)]
        total = sum(raw_intervals)
        norm = [x / total for x in raw_intervals]

        events = []
        t = 0.0
        for i, dt in enumerate(norm):
            key = SAFE_KEYS[i % len(SAFE_KEYS)]
            events.append({"type": "down", "key": key, "time": round(t, 6)})
            events.append({"type": "up",   "key": key, "time": round(t + dt * 0.5, 6)})
            t += dt

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(events, f, indent=2, ensure_ascii=False)

        status_cb(f"✅ 生成完畢！已儲存 (鍵: {SAFE_KEYS[0]})", "green")
    except Exception as e:
        status_cb(f"錯誤: {e}", "red")
    finally:
        done_cb()


# ── 錄製 ───────────────────────────────────────────────────────

def record_work(delay, record_sec, output_file, own_hwnd,
                stop_event, focus_enabled, status_cb, done_cb):
    try:
        target = wait_and_lock_target(
            delay, own_hwnd, stop_event, status_cb, focus_enabled)
        if stop_event.is_set() or target is None:
            return

        recorded = []
        start = time.time()
        pressed = set()

        def on_key(e):
            if stop_event.is_set():
                return
            t = round(time.time() - start, 6)
            if e.event_type == 'down' and e.name not in pressed:
                pressed.add(e.name)
                recorded.append({'type': 'down', 'key': e.name, 'time': t})
            elif e.event_type == 'up':
                pressed.discard(e.name)
                recorded.append({'type': 'up', 'key': e.name, 'time': t})

        status_cb(f"🔴 錄製中 (預計 {record_sec} 秒)...", "red")
        hook = keyboard.hook(on_key)

        end_t = time.time() + record_sec
        while time.time() < end_t and not stop_event.is_set():
            if focus_enabled and get_foreground() != target:
                stop_event.set()
                status_cb("⚠️ 偵測到視窗切換，錄製已中斷", "red")
                break
            time.sleep(0.01)

        keyboard.unhook(hook)

        if not stop_event.is_set():
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(recorded, f, indent=2, ensure_ascii=False)
            status_cb("✅ 錄製成功！", "green")
    except Exception as e:
        status_cb(f"錯誤: {e}", "red")
    finally:
        done_cb()


# ── 回放 ───────────────────────────────────────────────────────

def replay_work(input_file, loop_times, max_cps, delay, own_hwnd,
                stop_event, focus_enabled, status_cb, done_cb):
    try:
        if not os.path.exists(input_file):
            status_cb("❌ 錯誤：找不到 record.json", "red")
            return

        with open(input_file, 'r', encoding='utf-8') as f:
            events = json.load(f)

        if max_cps:
            min_gap = 1.0 / max_cps
            filtered, last_down = [], -1.0
            for ev in events:
                if ev['type'] == 'down':
                    if ev['time'] - last_down < min_gap:
                        continue
                    last_down = ev['time']
                filtered.append(ev)
            events = filtered

        target = wait_and_lock_target(
            delay, own_hwnd, stop_event, status_cb, focus_enabled)
        if stop_event.is_set() or target is None:
            return

        def on_focus_lost():
            stop_event.set()
            status_cb("⚠️ 偵測到視窗切換，已安全暫停", "red")

        for i in range(loop_times):
            if stop_event.is_set():
                break
            status_cb(f"▶ 回放中 ({i+1}/{loop_times})", "green")
            start_p = time.perf_counter()

            for ev in events:
                if stop_event.is_set():
                    break
                precise_sleep(
                    start_p + ev['time'] - time.perf_counter(),
                    target, stop_event, focus_enabled, on_focus_lost)
                if stop_event.is_set():
                    break
                try:
                    if ev['type'] == 'down':
                        key_down(ev['key'])
                    else:
                        key_up(ev['key'])
                except Exception:
                    pass

        for k in {e['key'] for e in events}:
            try:
                key_up(k)
            except Exception:
                pass

        if not stop_event.is_set():
            status_cb("✅ 回放結束", "blue")
    except Exception as e:
        status_cb(f"錯誤: {e}", "red")
    finally:
        done_cb()
