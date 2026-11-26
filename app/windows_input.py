"""Checked Win32 keyboard input for clipboard copy and paste."""

import ctypes


INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 1
KEYEVENTF_KEYUP = 2
VK_CONTROL = 0x11


def _input_type(ulong_ptr):
    """Use fixed-width Windows fields and a pointer-sized dwExtraInfo."""
    class MOUSEINPUT(ctypes.Structure):
        _fields_ = [('dx', ctypes.c_int32), ('dy', ctypes.c_int32),
                    ('mouseData', ctypes.c_uint32), ('dwFlags', ctypes.c_uint32),
                    ('time', ctypes.c_uint32), ('dwExtraInfo', ulong_ptr)]

    class KEYBDINPUT(ctypes.Structure):
        _fields_ = [('wVk', ctypes.c_uint16), ('wScan', ctypes.c_uint16),
                    ('dwFlags', ctypes.c_uint32), ('time', ctypes.c_uint32),
                    ('dwExtraInfo', ulong_ptr)]

    class HARDWAREINPUT(ctypes.Structure):
        _fields_ = [('uMsg', ctypes.c_uint32), ('wParamL', ctypes.c_uint16),
                    ('wParamH', ctypes.c_uint16)]

    class INPUT_UNION(ctypes.Union):
        _fields_ = [('mi', MOUSEINPUT), ('ki', KEYBDINPUT), ('hi', HARDWAREINPUT)]

    class INPUT(ctypes.Structure):
        _anonymous_ = ('value',)
        _fields_ = [('type', ctypes.c_uint32), ('value', INPUT_UNION)]

    return INPUT


INPUT = _input_type(ctypes.c_size_t)


def _user32():
    api = ctypes.WinDLL('user32', use_last_error=True)
    api.SendInput.argtypes = [ctypes.c_uint32, ctypes.POINTER(INPUT), ctypes.c_int]
    api.SendInput.restype = ctypes.c_uint32
    return api


class WindowsKeyboard:
    def __init__(self, api=None):
        self._api = api if api is not None else _user32()

    def _send(self, events):
        inputs = (INPUT * len(events))()
        for entry, (vk, flags) in zip(inputs, events):
            entry.type = INPUT_KEYBOARD
            entry.ki.wVk = vk
            entry.ki.dwFlags = flags
        sent = self._api.SendInput(len(inputs), inputs, ctypes.sizeof(INPUT))
        if sent != len(inputs):
            raise RuntimeError(
                f'Windows accepted {sent} of {len(inputs)} keyboard events. '
                'The target application may block simulated input. Check it before retrying.'
            )

    def release_modifiers(self):
        # Right Control/Alt and both Windows keys use extended key events.
        keys = [(0xA2, False), (0xA3, True), (0xA4, False), (0xA5, True),
                (0xA0, False), (0xA1, False), (0x5B, True), (0x5C, True)]
        self._send([(vk, KEYEVENTF_KEYUP | (KEYEVENTF_EXTENDEDKEY if extended else 0))
                    for vk, extended in keys])

    def shortcut(self, key):
        if key not in ('c', 'v'):
            raise ValueError('Only clipboard copy and paste shortcuts are supported.')
        vk = ord(key.upper())
        try:
            self._send([(VK_CONTROL, 0), (vk, 0),
                        (vk, KEYEVENTF_KEYUP), (VK_CONTROL, KEYEVENTF_KEYUP)])
        except Exception:
            # A partial SendInput may leave Control or the letter held down.
            # Attempt key-up events even when Windows rejects the original batch.
            try:
                self._send([(vk, KEYEVENTF_KEYUP), (VK_CONTROL, KEYEVENTF_KEYUP)])
            except Exception:
                pass
            raise
