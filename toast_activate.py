"""Replay native Windows toast clicks for Electron apps (Cursor, Discord, Equibop).

Electron registers a COM toast activator per app. A native Action Center click
calls Activate() with invoked_args like: type=click&tag=<electron-notification-id>

We invoke the same COM path from the custom tray when we have the tag.
When COM activation is unavailable from an external process, callers should
focus the running app window instead of launching a duplicate via shell:AppsFolder.
"""

from __future__ import annotations

import ctypes
import threading
import uuid
from ctypes import HRESULT, POINTER, byref, c_ulong, c_void_p, c_wchar_p, wintypes
from pathlib import Path

_CLSID_CACHE: dict[str, str] = {}
_CACHE_LOCK = threading.Lock()
_COM_INITIALIZED = False
_COM_LOCK = threading.Lock()

IID_IClassFactory = uuid.UUID("{00000001-0000-0000-C000-000000000046}")
IID_INotificationActivationCallback = uuid.UUID("{52BA54D7-BBAB-4B75-BA01-19A52640BE88}")
CLSCTX_LOCAL_SERVER = 4


class GUID(ctypes.Structure):
    _fields_ = [
        ("Data1", wintypes.DWORD),
        ("Data2", wintypes.WORD),
        ("Data3", wintypes.WORD),
        ("Data4", wintypes.BYTE * 8),
    ]


def _to_guid(value: str | uuid.UUID) -> GUID:
    parsed = value if isinstance(value, uuid.UUID) else uuid.UUID(str(value).strip("{}"))
    return GUID(
        parsed.time_low,
        parsed.time_mid,
        parsed.time_hi_version,
        (wintypes.BYTE * 8)(*parsed.bytes[8:]),
    )


def _ensure_com_initialized() -> None:
    global _COM_INITIALIZED
    with _COM_LOCK:
        if _COM_INITIALIZED:
            return
        ctypes.OleDLL("ole32").CoInitialize(None)
        _COM_INITIALIZED = True


def _read_shortcut_clsid(lnk_path: Path) -> tuple[str, str]:
    import pythoncom
    from win32com.propsys import propsys
    from win32com.shell import shell

    shortcut = pythoncom.CoCreateInstance(
        shell.CLSID_ShellLink, None, pythoncom.CLSCTX_INPROC_SERVER, shell.IID_IShellLink
    )
    persist = shortcut.QueryInterface(pythoncom.IID_IPersistFile)
    persist.Load(str(lnk_path))
    store = shortcut.QueryInterface(propsys.IID_IPropertyStore)

    aumid_key = propsys.PSGetPropertyKeyFromName("System.AppUserModel.ID")
    clsid_key = propsys.PSGetPropertyKeyFromName("System.AppUserModel.ToastActivatorCLSID")
    aumid = store.GetValue(aumid_key).GetValue() or ""
    clsid = store.GetValue(clsid_key).GetValue() or ""
    return aumid, clsid


def _scan_start_menu_shortcuts() -> None:
    roots = [
        Path.home() / "AppData/Roaming/Microsoft/Windows/Start Menu/Programs",
        Path.home() / "AppData/Local/Microsoft/Windows/Start Menu/Programs",
    ]

    for root in roots:
        if not root.exists():
            continue
        for lnk in root.rglob("*.lnk"):
            try:
                aumid, clsid = _read_shortcut_clsid(lnk)
                if aumid and clsid:
                    _CLSID_CACHE[aumid] = clsid
            except Exception:
                continue


def get_toast_activator_clsid(aumid: str) -> str:
    if not aumid:
        return ""
    with _CACHE_LOCK:
        if not _CLSID_CACHE:
            _scan_start_menu_shortcuts()
        return _CLSID_CACHE.get(aumid, "")


def build_click_args(tag: str, activation_type: str = "click") -> str:
    tag = (tag or "").strip()
    if not tag:
        return ""
    return f"type={activation_type}&tag={tag}"


def _com_method(this: int, slot: int, restype, *argtypes):
    vtbl = ctypes.cast(this, POINTER(c_void_p))[0]
    slots = ctypes.cast(vtbl, POINTER(c_void_p * (slot + 1))).contents
    return ctypes.WINFUNCTYPE(restype, c_void_p, *argtypes)(slots[slot])


def _activate_via_com(clsid: str, aumid: str, invoked_args: str) -> bool:
    """Call IClassFactory::CreateInstance + INotificationActivationCallback::Activate."""
    ole32 = ctypes.OleDLL("ole32")
    clsid_guid = _to_guid(clsid)
    factory = c_void_p()

    hr = ole32.CoGetClassObject(
        byref(clsid_guid),
        CLSCTX_LOCAL_SERVER,
        None,
        byref(_to_guid(IID_IClassFactory)),
        byref(factory),
    )
    if hr != 0 or not factory.value:
        return False

    create_instance = _com_method(
        factory.value,
        3,
        HRESULT,
        c_void_p,
        POINTER(GUID),
        POINTER(c_void_p),
    )
    callback = c_void_p()
    hr = create_instance(
        factory.value,
        None,
        byref(_to_guid(IID_INotificationActivationCallback)),
        byref(callback),
    )
    if hr != 0 or not callback.value:
        return False

    activate = _com_method(
        callback.value,
        3,
        HRESULT,
        c_wchar_p,
        c_wchar_p,
        c_void_p,
        c_ulong,
    )
    hr = activate(callback.value, aumid, invoked_args, None, 0)
    return hr == 0


def activate_native_toast(aumid: str, tag: str, activation_type: str = "click") -> bool:
    """Invoke an app's Electron toast COM activator (same path as a native click)."""
    aumid = (aumid or "").strip()
    invoked_args = build_click_args(tag, activation_type)
    if not aumid or not invoked_args:
        return False

    clsid = get_toast_activator_clsid(aumid)
    if not clsid:
        print(f"[toast_activate] No toast activator CLSID found for {aumid}")
        return False

    _ensure_com_initialized()

    try:
        if _activate_via_com(clsid, aumid, invoked_args):
            return True
        print(f"[toast_activate] COM Activate failed for {aumid} (clsid={clsid})")
        return False
    except Exception as exc:
        print(f"[toast_activate] COM activation failed for {aumid}: {exc}")
        return False
