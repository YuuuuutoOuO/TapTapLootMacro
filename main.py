import tkinter as tk
from tkinter import ttk, simpledialog
import threading
import keyboard
import time
import json
import os
import sys
import pydirectinput
import random
import ctypes

# === 環境路徑處理 (解決 EXE 路徑消失問題) ===
def get_base_path():
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))

SCRIPT_DIR = get_base_path()
INPUT_FILE = os.path.join(SCRIPT_DIR, "record.json") 
SETTING_FILE = os.path.join(SCRIPT_DIR, "setting.json") 

# 核心優化：關閉 pydirectinput 預設延遲
pydirectinput.PAUSE = 0

class MacroApp:
    def __init__(self, root):
        self.root = root
        self.root.title("TapTapLoot點擊腳本")
        self.root.geometry("440x580")
        self.root.resizable(False, False)
        
        self.is_running = False
        self.stop_event = threading.Event()
        self.cps_to_generate = 20 
        
        self.settings = self.init_settings()
        self.setup_ui()
        
        # 註冊 F9 緊急中斷全域熱鍵
        keyboard.add_hotkey('f9', lambda: self.trigger_stop())
        
    def init_settings(self):
        default = {
            "REPLAY_TIMES": 999,
            "DELAY_BEFORE_START": 5,
            "RECORD_SECONDS": 10,
            "LIMIT_CPS_ENABLED": False,
            "MAX_CPS": 100,
            "STOP_ON_FOCUS_LOST": True 
        }
        if not os.path.exists(SETTING_FILE):
            try:
                with open(SETTING_FILE, 'w', encoding='utf-8') as f:
                    json.dump(default, f, indent=4, ensure_ascii=False)
            except: pass
            return default
            
        try:
            with open(SETTING_FILE, 'r', encoding='utf-8') as f:
                return {**default, **json.load(f)}
        except:
            return default

    def save_current_settings(self):
        try:
            self.settings.update({
                "REPLAY_TIMES": int(self.replay_times_var.get()),
                "DELAY_BEFORE_START": int(self.delay_var.get()),
                "RECORD_SECONDS": int(self.record_sec_var.get()),
                "LIMIT_CPS_ENABLED": self.cps_enable_var.get(),
                "MAX_CPS": int(self.max_cps_var.get()),
                "STOP_ON_FOCUS_LOST": self.focus_stop_var.get()
            })
            with open(SETTING_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.settings, f, indent=4, ensure_ascii=False)
        except: pass

    def trigger_stop(self, reason="🚨 已手動強制中斷！"):
        """觸發中斷，支援自訂中斷原因"""
        if self.is_running:
            self.stop_event.set()
            self.root.after(0, lambda: self.update_status(reason, "red"))

    def setup_ui(self):
        container = ttk.Frame(self.root, padding=15)
        container.pack(fill="both", expand=True)

        mode_frame = ttk.LabelFrame(container, text="工作模式", padding=5)
        mode_frame.pack(fill="x", pady=5)
        self.mode_var = tk.StringVar(value="replay")
        
        ttk.Radiobutton(mode_frame, text="回放 (Replay)", variable=self.mode_var, value="replay").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Radiobutton(mode_frame, text="錄製 (Record)", variable=self.mode_var, value="record").grid(row=0, column=1, padx=5, pady=2, sticky="w")
        ttk.Radiobutton(mode_frame, text="自動生成腳本", variable=self.mode_var, value="generate").grid(row=0, column=2, padx=5, pady=2, sticky="w")

        param_frame = ttk.LabelFrame(container, text="參數設定 (將自動儲存)", padding=10)
        param_frame.pack(fill="x", pady=5)

        self.record_sec_var = tk.StringVar(value=str(self.settings["RECORD_SECONDS"]))
        self.create_field(param_frame, "錄製總秒數:", self.record_sec_var, 0)

        self.replay_times_var = tk.StringVar(value=str(self.settings["REPLAY_TIMES"]))
        self.create_field(param_frame, "回放次數:", self.replay_times_var, 1)

        self.delay_var = tk.StringVar(value=str(self.settings["DELAY_BEFORE_START"]))
        self.create_field(param_frame, "啟動延遲 (秒):", self.delay_var, 2)

        self.cps_enable_var = tk.BooleanVar(value=self.settings["LIMIT_CPS_ENABLED"])
        ttk.Checkbutton(param_frame, text="啟用每秒點擊上限", variable=self.cps_enable_var).grid(row=3, column=0, pady=5, sticky="w")
        self.max_cps_var = tk.StringVar(value=str(self.settings["MAX_CPS"]))
        ttk.Entry(param_frame, textvariable=self.max_cps_var, width=8).grid(row=3, column=1, sticky="w", padx=5)

        self.focus_stop_var = tk.BooleanVar(value=self.settings["STOP_ON_FOCUS_LOST"])
        ttk.Checkbutton(param_frame, text="失去視窗焦點時自動暫停 (防誤觸)", variable=self.focus_stop_var).grid(row=4, column=0, columnspan=2, pady=5, sticky="w")

        self.status_label = ttk.Label(container, text="狀態: 準備就緒", font=("", 10, "bold"), foreground="blue")
        self.status_label.pack(pady=10)
        ttk.Label(container, text="執行中可按 F9 鍵 或 點擊停止按鈕", foreground="gray", font=("", 9)).pack()

        btn_frame = ttk.Frame(container)
        btn_frame.pack(pady=10, fill="x")
        
        self.run_btn = ttk.Button(btn_frame, text="▶ 開始執行", command=self.start_thread)
        self.run_btn.pack(side="left", fill="x", expand=True, padx=5)
        
        self.stop_btn = ttk.Button(btn_frame, text="⏹ 停止執行", command=lambda: self.trigger_stop(), state="disabled")
        self.stop_btn.pack(side="right", fill="x", expand=True, padx=5)

    def create_field(self, parent, label, var, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(parent, textvariable=var, width=12).grid(row=row, column=1, sticky="w", padx=5)

    def update_status(self, msg, color="black"):
        self.status_label.config(text=f"狀態: {msg}", foreground=color)
        self.root.update()

    def start_thread(self):
        if self.is_running: return
        
        mode = self.mode_var.get()
        if mode == "generate":
            cps = simpledialog.askinteger("自動生成腳本", "請輸入每秒點擊次數 (例如 20):", parent=self.root, minvalue=1, maxvalue=500)
            if not cps: return
            self.cps_to_generate = cps

        self.save_current_settings()
        self.stop_event.clear()
        self.is_running = True
        
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")
        
        if mode == "record": target = self.record_work
        elif mode == "replay": target = self.replay_work
        else: target = self.generate_work
            
        threading.Thread(target=target, daemon=True).start()

    def wait_and_lock_target(self, delay_seconds):
        """核心修復：倒數期間智慧監控視窗焦點"""
        ui_hwnd = ctypes.windll.user32.GetForegroundWindow()
        target_hwnd = None

        for d in range(delay_seconds, 0, -1):
            if self.stop_event.is_set(): return None

            if target_hwnd:
                self.root.after(0, lambda val=d: self.update_status(f"🎯 已鎖定視窗，倒數 {val} 秒...", "orange"))
            else:
                self.root.after(0, lambda val=d: self.update_status(f"⏳ 請切換至目標視窗... 倒數 {val} 秒", "orange"))

            end_t = time.perf_counter() + 1.0
            # 將 1 秒的等待切分為每 10ms 檢查一次
            while time.perf_counter() < end_t:
                if self.stop_event.is_set(): return None

                if self.focus_stop_var.get():
                    curr_hwnd = ctypes.windll.user32.GetForegroundWindow()
                    
                    if target_hwnd is None:
                        # 只要使用者離開了 UI 介面，就立刻將新視窗登記為目標！
                        if curr_hwnd != ui_hwnd and curr_hwnd != 0:
                            target_hwnd = curr_hwnd
                            self.root.after(0, lambda val=d: self.update_status(f"🎯 提早鎖定視窗！倒數 {val} 秒...", "orange"))
                    else:
                        # 如果已經鎖定目標，但使用者又切走了，立刻引爆安全機制
                        if curr_hwnd != target_hwnd:
                            self.trigger_stop("⚠️ 倒數期間切換視窗，已安全取消！")
                            return None
                            
                time.sleep(0.01)

        # 若倒數結束使用者都沒切換，就以當下視窗為主
        if target_hwnd is None:
            target_hwnd = ctypes.windll.user32.GetForegroundWindow()

        return target_hwnd

    def precise_sleep(self, duration, target_hwnd=None):
        """高精度延遲，期間不間斷偵測失焦"""
        if duration <= 0: return
        end_time = time.perf_counter() + duration
        
        while end_time - time.perf_counter() > 0.015:
            if self.stop_event.is_set(): return
            if target_hwnd and self.focus_stop_var.get():
                if ctypes.windll.user32.GetForegroundWindow() != target_hwnd:
                    self.trigger_stop("⚠️ 偵測到視窗切換，已安全暫停")
                    return
            time.sleep(0.01)

        while time.perf_counter() < end_time:
            if self.stop_event.is_set(): return
            if target_hwnd and self.focus_stop_var.get():
                if ctypes.windll.user32.GetForegroundWindow() != target_hwnd:
                    self.trigger_stop("⚠️ 偵測到視窗切換，已安全暫停")
                    return

    def generate_work(self):
        try:
            self.update_status(f"⚙️ 正在生成腳本 ({self.cps_to_generate} 下/秒)...", "blue")
            n_clicks = self.cps_to_generate
            
            raw_intervals = [random.uniform(0.5, 1.5) for _ in range(n_clicks)]
            total_raw = sum(raw_intervals)
            norm_intervals = [x / total_raw for x in raw_intervals]
            
            events = []
            curr_time = 0.0
            
            for i in range(n_clicks):
                key = str(i % 10)
                down_time = curr_time
                up_time = curr_time + (norm_intervals[i] * 0.5)
                events.append({"type": "down", "key": key, "time": round(down_time, 6)})
                events.append({"type": "up", "key": key, "time": round(up_time, 6)})
                curr_time += norm_intervals[i]
                
            with open(INPUT_FILE, 'w', encoding='utf-8') as f:
                json.dump(events, f, indent=2, ensure_ascii=False)
                
            self.root.after(0, lambda: self.update_status("✅ 生成完畢！已儲存", "green"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"錯誤: {e}", "red"))
        finally:
            self.root.after(0, self.reset_ui)

    def record_work(self):
        try:
            delay = int(self.delay_var.get())
            sec = int(self.record_sec_var.get())
            
            # 使用全新的智慧鎖定倒數機制
            target_hwnd = self.wait_and_lock_target(delay)
            if self.stop_event.is_set() or target_hwnd is None:
                return
            
            recorded_data = []
            start_t = time.time()
            pressed = set()

            def on_key(e):
                if self.stop_event.is_set(): return
                t = round(time.time() - start_t, 6)
                if e.event_type == 'down' and e.name not in pressed:
                    pressed.add(e.name)
                    recorded_data.append({'type': 'down', 'key': e.name, 'time': t})
                elif e.event_type == 'up':
                    pressed.discard(e.name)
                    recorded_data.append({'type': 'up', 'key': e.name, 'time': t})

            self.root.after(0, lambda: self.update_status(f"🔴 錄製中 (預計 {sec} 秒)...", "red"))
            hook = keyboard.hook(on_key)
            
            end_limit = time.time() + sec
            while time.time() < end_limit and not self.stop_event.is_set():
                if self.focus_stop_var.get() and ctypes.windll.user32.GetForegroundWindow() != target_hwnd:
                    self.trigger_stop("⚠️ 偵測到視窗切換，錄製已中斷")
                    break
                time.sleep(0.01)
                
            keyboard.unhook(hook)
            
            if not self.stop_event.is_set():
                with open(INPUT_FILE, 'w', encoding='utf-8') as f:
                    json.dump(recorded_data, f, indent=2, ensure_ascii=False)
                self.root.after(0, lambda: self.update_status(f"✅ 錄製成功！", "green"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"錯誤: {e}", "red"))
        finally:
            self.root.after(0, self.reset_ui)

    def replay_work(self):
        try:
            if not os.path.exists(INPUT_FILE):
                self.root.after(0, lambda: self.update_status("❌ 錯誤：找不到 record.json", "red"))
                return
            with open(INPUT_FILE, 'r', encoding='utf-8') as f:
                events = json.load(f)

            if self.cps_enable_var.get():
                min_gap = 1.0 / int(self.max_cps_var.get())
                filtered = []
                last_down = -1.0
                for ev in events:
                    if ev['type'] == 'down':
                        if ev['time'] - last_down < min_gap: continue
                        last_down = ev['time']
                    filtered.append(ev)
                events = filtered

            delay = int(self.delay_var.get())
            
            # 使用全新的智慧鎖定倒數機制
            target_hwnd = self.wait_and_lock_target(delay)
            if self.stop_event.is_set() or target_hwnd is None:
                return

            loop_times = int(self.replay_times_var.get())
            
            for i in range(loop_times):
                if self.stop_event.is_set(): break
                self.root.after(0, lambda: self.update_status(f"▶ 回放中 ({i+1}/{loop_times})", "green"))
                start_p = time.perf_counter()
                
                for ev in events:
                    if self.stop_event.is_set(): break
                    target = start_p + ev['time']
                    
                    self.precise_sleep(target - time.perf_counter(), target_hwnd)
                    if self.stop_event.is_set(): break
                    
                    try:
                        if ev['type'] == 'down': pydirectinput.keyDown(ev['key'])
                        else: pydirectinput.keyUp(ev['key'])
                    except: pass
            
            for k in set(e['key'] for e in events): pydirectinput.keyUp(k)
            if not self.stop_event.is_set():
                self.root.after(0, lambda: self.update_status("✅ 回放結束", "blue"))
        except Exception as e:
            self.root.after(0, lambda: self.update_status(f"錯誤: {e}", "red"))
        finally:
            self.root.after(0, self.reset_ui)

    def reset_ui(self):
        self.is_running = False
        self.run_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

if __name__ == '__main__':
    root = tk.Tk()
    app = MacroApp(root)
    root.mainloop()