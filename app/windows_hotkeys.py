"""Windows-owned hotkeys delivered through Qt's existing message loop."""

import ctypes
from ctypes import wintypes
from itertools import count

from PySide6.QtCore import QAbstractNativeEventFilter, QCoreApplication
from pynput import keyboard


MOD_NOREPEAT = 0x4000
WM_HOTKEY = 0x0312
_ids = count(0x5100)
_modifier_bits = {
    keyboard.Key.alt: 1, keyboard.Key.ctrl: 2,
    keyboard.Key.shift: 4, keyboard.Key.cmd: 8,
}


def _user32():
    api = ctypes.WinDLL('user32', use_last_error=True)
    api.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.UINT, wintypes.UINT]
    api.RegisterHotKey.restype = wintypes.BOOL
    api.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    api.UnregisterHotKey.restype = wintypes.BOOL
    api.VkKeyScanW.argtypes = [wintypes.WCHAR]
    api.VkKeyScanW.restype = ctypes.c_short
    return api


def shortcut_spec(chord, api=None):
    """Resolve a chord without registering it, for validation before saving."""
    modifiers, vk = 0, None
    for key in chord:
        if key in _modifier_bits:
            modifiers |= _modifier_bits[key]
        elif getattr(key, 'vk', None) is not None:
            vk = key.vk
        elif getattr(key, 'char', None) is not None:
            try:
                mapped = (api or _user32()).VkKeyScanW(key.char)
            except (TypeError, ValueError, ctypes.ArgumentError) as exc:
                raise ValueError('The shortcut key is unavailable on this keyboard layout.') from exc
            if mapped == -1:
                raise ValueError('The shortcut key is unavailable on this keyboard layout.')
            vk = mapped & 0xff
            # VkKeyScan uses shift/control/alt bits; RegisterHotKey uses alt/control/shift.
            state = (mapped >> 8) & 7
            modifiers |= (4 if state & 1 else 0) | (2 if state & 2 else 0) | (1 if state & 4 else 0)
    if vk is None or not 1 <= vk <= 254:
        raise ValueError('The shortcut needs a valid Windows key.')
    if vk == 0x7b:
        raise ValueError('F12 is reserved by Windows for debugging. Choose another key.')
    return modifiers, vk


class WindowsHotkeys(QAbstractNativeEventFilter):
    """Register only configured chords; never track ordinary keystrokes."""

    def __init__(self):
        super().__init__()
        self._app = QCoreApplication.instance()
        if self._app is None:
            raise RuntimeError('Hotkeys require the application message loop.')
        self._api = _user32()
        self._registrations = {}
        self._callbacks = {}
        self._installed = False

    @property
    def running(self):
        return bool(self._callbacks)

    def set_bindings(self, bindings):
        requested = {}
        for chord, callback in bindings.items():
            spec = shortcut_spec(chord, self._api)
            if spec in requested:
                raise ValueError('The shortcuts resolve to the same Windows key combination.')
            requested[spec] = callback
        added = {}
        if not self._installed:
            self._app.installNativeEventFilter(self)
            self._installed = True
        try:
            for spec in requested:
                if spec not in self._registrations:
                    identifier = next(_ids)
                    if identifier > 0xBFFF:
                        raise RuntimeError('Windows hotkey identifiers exhausted. Restart Quill.')
                    modifiers, vk = spec
                    if not self._api.RegisterHotKey(None, identifier, modifiers | MOD_NOREPEAT, vk):
                        error = ctypes.get_last_error()
                        raise RuntimeError(
                            f'Windows could not register a shortcut (error {error}). '
                            'Another application may already use it. Choose another shortcut in Settings.'
                        )
                    added[spec] = identifier
        except Exception:
            for identifier in added.values():
                self._api.UnregisterHotKey(None, identifier)
            if not self._registrations:
                self._app.removeNativeEventFilter(self)
                self._installed = False
            raise
        registrations = {spec: self._registrations.get(spec, added.get(spec)) for spec in requested}
        for spec, identifier in self._registrations.items():
            if spec not in requested:
                self._api.UnregisterHotKey(None, identifier)
        self._registrations = registrations
        self._callbacks = {registrations[spec]: callback for spec, callback in requested.items()}

    def nativeEventFilter(self, event_type, message):
        if bytes(event_type) not in (b'windows_generic_MSG', b'windows_dispatcher_MSG'):
            return False, 0
        msg = wintypes.MSG.from_address(int(message))
        callback = self._callbacks.get(msg.wParam) if msg.message == WM_HOTKEY else None
        if callback is None:
            return False, 0
        callback()
        return True, 0

    def stop(self):
        for identifier in self._registrations.values():
            self._api.UnregisterHotKey(None, identifier)
        self._registrations.clear()
        self._callbacks.clear()
        if self._installed:
            self._app.removeNativeEventFilter(self)
            self._installed = False
