"""
main.py — 程式進入點
執行方式: python main.py  或打包後直接執行 exe

資料夾結構（放在同一層）：
  main.py
  ICON.ico
  macro_app/
    core/...
    ui/...
"""

import os
import sys
import tkinter as tk
from ui.main_window import MacroApp


def get_base_path() -> str:
    """取得 exe / 原始碼所在目錄（record.json、setting.json 寫在這裡）"""
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_asset_path(filename: str) -> str:
    """
    取得打包進 EXE 內部的資源路徑。
    PyInstaller 打包時用 --add-data 把 ICON.ico 加進去，
    執行時會解壓到 sys._MEIPASS 暫存資料夾。
    開發環境則直接讀同層目錄。
    """
    try:
        base = sys._MEIPASS          # PyInstaller 打包後的暫存路徑
    except AttributeError:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, filename)


if __name__ == "__main__":
    base = get_base_path()
    root = tk.Tk()

    # ── 設定視窗 ICON ────────────────────────────────────────────
    icon_path = get_asset_path("ICON.ico")
    if os.path.exists(icon_path):
        root.iconbitmap(icon_path)
    else:
        print(f"[警告] 找不到圖示: {icon_path}")

    app = MacroApp(
        root,
        setting_file=os.path.join(base, "setting.json"),
        input_file=os.path.join(base, "record.json"),
    )
    root.mainloop()
