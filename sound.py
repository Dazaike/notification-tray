"""Plays the notification sound effect via the Windows MCI API (supports mp3)."""

import ctypes
import threading

import config

_play_counter = 0
_play_lock = threading.Lock()


def _play(path):
    global _play_counter
    winmm = ctypes.windll.winmm
    with _play_lock:
        _play_counter += 1
        alias = f"notif_{threading.get_ident()}_{_play_counter}"
    try:
        winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, 0)
        winmm.mciSendStringW(f"play {alias} wait", None, 0, 0)
        winmm.mciSendStringW(f"close {alias}", None, 0, 0)
    except Exception:
        pass


def play_notification_sound():
    path = config.NOTIFICATION_SOUND
    if not path:
        return
    threading.Thread(target=_play, args=(path,), daemon=True).start()
