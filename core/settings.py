"""
settings.py
===========
負責設定檔的讀取與寫入。
"""

import json
import os

DEFAULT: dict = {
    "REPLAY_TIMES": 999,
    "DELAY_BEFORE_START": 5,
    "RECORD_SECONDS": 10,
    "LIMIT_CPS_ENABLED": False,
    "MAX_CPS": 100,
    "STOP_ON_FOCUS_LOST": True,
    "IDLE_DETECT_ENABLED": False,
    "IDLE_MINUTES": 5.0,
}


def load(path: str) -> dict:
    if not os.path.exists(path):
        save(path, DEFAULT)
        return dict(DEFAULT)
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return {**DEFAULT, **json.load(f)}
    except Exception:
        return dict(DEFAULT)


def save(path: str, data: dict):
    try:
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
