"""Plays the notification sound effect via the Windows MCI API (supports mp3)."""

import ctypes
import threading
import applog
import config

_play_counter = 0
_play_lock = threading.Lock()


def _play(path: str):
    global _play_counter
    winmm = ctypes.windll.winmm
    with _play_lock:
        _play_counter += 1
        alias = f"notif_{threading.get_ident()}_{_play_counter}"
    try:
        ret = winmm.mciSendStringW(f'open "{path}" type mpegvideo alias {alias}', None, 0, 0)
        if ret != 0:
            ret = winmm.mciSendStringW(f'open "{path}" alias {alias}', None, 0, 0)
        if ret != 0:
            applog.get_logger().warning("mciSendString open failed with error code %s for %s", ret, path)
            return
        winmm.mciSendStringW(f"setaudio {alias} volume to 1000", None, 0, 0)
        winmm.mciSendStringW(f"play {alias} wait", None, 0, 0)
        winmm.mciSendStringW(f"close {alias}", None, 0, 0)
    except Exception:
        applog.get_logger().exception("sound playback error")


def play_notification_sound(custom_path: str = ""):
    from pathlib import Path
    path = ""
    if custom_path and Path(custom_path).exists():
        path = str(custom_path)
    elif config.NOTIFICATION_SOUND and Path(config.NOTIFICATION_SOUND).exists():
        path = config.NOTIFICATION_SOUND
    else:
        sound_file = config.resource_path("fears-to-fathom-notification.mp3")
        if sound_file.exists():
            path = str(sound_file)
            config.NOTIFICATION_SOUND = path
        else:
            applog.get_logger().warning("Notification sound file not found: %s", sound_file)
            return
    threading.Thread(target=_play, args=(path,), daemon=True).start()
