"""
main_window.py
==============
MacroApp 主視窗：只負責 UI 建立與事件路由，
所有業務邏輯都委派給 core/ 模組。
"""

import threading
import tkinter as tk
from tkinter import ttk, simpledialog

import keyboard

from core import settings as cfg
from core.idle_detector import IdleDetector
from core.window_focus import get_foreground, set_foreground
from core import workers


class MacroApp:
    def __init__(self, root: tk.Tk, setting_file: str, input_file: str):
        self.root = root
        self.root.title("TapTapLootMacro")
        self.root.geometry("440x650")
        self.root.resizable(False, False)

        self._setting_file = setting_file
        self._input_file = input_file

        self.is_running = False
        self.stop_event = threading.Event()
        self.cps_to_generate = 20

        self.settings = cfg.load(setting_file)

        self._idle = IdleDetector(status_cb=self.update_status)

        self._build_ui()

        keyboard.add_hotkey('f9', lambda: self.trigger_stop())

        # 綁定使用者活動通知（供掛機偵測）
        keyboard.hook(lambda e: self._idle.notify_activity())
        self.root.bind("<Motion>", lambda e: self._idle.notify_activity())
        self.root.bind("<Button>", lambda e: self._idle.notify_activity())

    # =========================================================
    # UI 建立
    # =========================================================
    def _build_ui(self):
        s = self.settings
        container = ttk.Frame(self.root, padding=15)
        container.pack(fill="both", expand=True)

        # 工作模式
        mf = ttk.LabelFrame(container, text="工作模式", padding=5)
        mf.pack(fill="x", pady=5)
        self.mode_var = tk.StringVar(value="replay")
        ttk.Radiobutton(mf, text="回放 (Replay)", variable=self.mode_var, value="replay").grid(row=0, column=0, padx=5, pady=2, sticky="w")
        ttk.Radiobutton(mf, text="錄製 (Record)", variable=self.mode_var, value="record").grid(row=0, column=1, padx=5, pady=2, sticky="w")
        ttk.Radiobutton(mf, text="自動生成腳本", variable=self.mode_var, value="generate").grid(row=0, column=2, padx=5, pady=2, sticky="w")

        # 參數
        pf = ttk.LabelFrame(container, text="參數設定 (即時自動儲存)", padding=10)
        pf.pack(fill="x", pady=5)

        self.record_sec_var  = tk.StringVar(value=str(s["RECORD_SECONDS"]))
        self.replay_times_var= tk.StringVar(value=str(s["REPLAY_TIMES"]))
        self.delay_var       = tk.StringVar(value=str(s["DELAY_BEFORE_START"]))
        self.cps_enable_var  = tk.BooleanVar(value=s["LIMIT_CPS_ENABLED"])
        self.max_cps_var     = tk.StringVar(value=str(s["MAX_CPS"]))
        self.focus_stop_var  = tk.BooleanVar(value=s["STOP_ON_FOCUS_LOST"])
        self.idle_enable_var = tk.BooleanVar(value=s["IDLE_DETECT_ENABLED"])
        self.idle_minutes_var= tk.StringVar(value=str(s["IDLE_MINUTES"]))

        for v in (self.record_sec_var, self.replay_times_var, self.delay_var,
                  self.max_cps_var, self.idle_minutes_var):
            v.trace_add("write", self._save)
        for v in (self.cps_enable_var, self.focus_stop_var, self.idle_enable_var):
            v.trace_add("write", self._save)

        self._field(pf, "錄製總秒數:",    self.record_sec_var,  0)
        self._field(pf, "回放次數:",      self.replay_times_var,1)
        self._field(pf, "啟動延遲 (秒):", self.delay_var,       2)
        ttk.Checkbutton(pf, text="啟用每秒點擊上限", variable=self.cps_enable_var).grid(row=3, column=0, pady=5, sticky="w")
        ttk.Entry(pf, textvariable=self.max_cps_var, width=8).grid(row=3, column=1, sticky="w", padx=5)
        ttk.Checkbutton(pf, text="失去焦點時自動暫停 (切換任何視窗皆暫停)",
                        variable=self.focus_stop_var).grid(row=4, column=0, columnspan=2, pady=5, sticky="w")

        # 掛機偵測
        idf = ttk.LabelFrame(container, text="掛機偵測", padding=8)
        idf.pack(fill="x", pady=5)
        ttk.Checkbutton(idf, text="啟用掛機偵測：無動作超過", variable=self.idle_enable_var).grid(row=0, column=0, sticky="w")
        ttk.Entry(idf, textvariable=self.idle_minutes_var, width=6).grid(row=0, column=1, padx=4, sticky="w")
        ttk.Label(idf, text="分鐘後自動開始輸出").grid(row=0, column=2, sticky="w")
        ttk.Label(idf, text="(使用者回來操作即自動停止)", foreground="gray", font=("", 8)).grid(row=1, column=0, columnspan=3, sticky="w")

        # 狀態 & 按鈕
        self.status_label = ttk.Label(container, text="狀態: 準備就緒",
                                      font=("", 10, "bold"), foreground="blue")
        self.status_label.pack(pady=8)
        ttk.Label(container, text="執行中可按 F9 鍵 或 點擊停止按鈕",
                  foreground="gray", font=("", 9)).pack()

        bf = ttk.Frame(container)
        bf.pack(pady=8, fill="x")
        self.run_btn  = ttk.Button(bf, text="▶ 開始執行", command=self.start_thread)
        self.run_btn.pack(side="left",  fill="x", expand=True, padx=5)
        self.stop_btn = ttk.Button(bf, text="⏹ 停止執行",
                                   command=lambda: self.trigger_stop(), state="disabled")
        self.stop_btn.pack(side="right", fill="x", expand=True, padx=5)

    def _field(self, parent, label, var, row):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", pady=2)
        ttk.Entry(parent, textvariable=var, width=12).grid(row=row, column=1, sticky="w", padx=5)

    # =========================================================
    # 設定
    # =========================================================
    def _save(self, *_):
        try:
            self.settings.update({
                "REPLAY_TIMES":       int(self.replay_times_var.get() or 0),
                "DELAY_BEFORE_START": int(self.delay_var.get() or 0),
                "RECORD_SECONDS":     int(self.record_sec_var.get() or 0),
                "LIMIT_CPS_ENABLED":  self.cps_enable_var.get(),
                "MAX_CPS":            int(self.max_cps_var.get() or 0),
                "STOP_ON_FOCUS_LOST": self.focus_stop_var.get(),
                "IDLE_DETECT_ENABLED":self.idle_enable_var.get(),
                "IDLE_MINUTES":       float(self.idle_minutes_var.get() or 1),
            })
            cfg.save(self._setting_file, self.settings)

            # 同步掛機偵測器
            self._idle.set_enabled(self.idle_enable_var.get())
            self._idle.set_threshold_minutes(float(self.idle_minutes_var.get() or 1))
        except (ValueError, Exception):
            pass

    # =========================================================
    # 狀態 & 控制
    # =========================================================
    def update_status(self, msg, color="black"):
        self.root.after(0, lambda: self.status_label.config(
            text=f"狀態: {msg}", foreground=color))

    def trigger_stop(self, reason="🚨 已手動強制中斷！"):
        if self.is_running:
            self.stop_event.set()
            self.update_status(reason, "red")

    def _reset_ui(self):
        self.is_running = False
        self.run_btn.config(state="normal")
        self.stop_btn.config(state="disabled")

    # =========================================================
    # 啟動
    # =========================================================
    def start_thread(self):
        if self.is_running:
            return
        mode = self.mode_var.get()
        if mode == "generate":
            cps = simpledialog.askinteger(
                "自動生成腳本",
                "請輸入每秒點擊次數（例如 20）\n注意次數過高可能導致系統異常:",
                parent=self.root, minvalue=1, maxvalue=2147483647)
            if not cps:
                return
            self.cps_to_generate = cps

        self._save()
        self.stop_event.clear()
        self.is_running = True
        self.run_btn.config(state="disabled")
        self.stop_btn.config(state="normal")

        own_hwnd = get_foreground()   # 呼叫時焦點在本程式 UI
        s = self.settings

        if mode == "generate":
            t = threading.Thread(target=workers.generate_work, daemon=True, kwargs=dict(
                cps=self.cps_to_generate,
                output_file=self._input_file,
                stop_event=self.stop_event,
                status_cb=self.update_status,
                done_cb=lambda: self.root.after(0, self._reset_ui),
            ))
        elif mode == "record":
            t = threading.Thread(target=workers.record_work, daemon=True, kwargs=dict(
                delay=s["DELAY_BEFORE_START"],
                record_sec=s["RECORD_SECONDS"],
                output_file=self._input_file,
                own_hwnd=own_hwnd,
                stop_event=self.stop_event,
                focus_enabled=s["STOP_ON_FOCUS_LOST"],
                status_cb=self.update_status,
                done_cb=lambda: self.root.after(0, self._reset_ui),
            ))
        else:  # replay
            t = threading.Thread(target=workers.replay_work, daemon=True, kwargs=dict(
                input_file=self._input_file,
                loop_times=s["REPLAY_TIMES"],
                max_cps=s["MAX_CPS"] if s["LIMIT_CPS_ENABLED"] else None,
                delay=s["DELAY_BEFORE_START"],
                own_hwnd=own_hwnd,
                stop_event=self.stop_event,
                focus_enabled=s["STOP_ON_FOCUS_LOST"],
                status_cb=self.update_status,
                done_cb=lambda: self.root.after(0, self._reset_ui),
            ))
        t.start()
