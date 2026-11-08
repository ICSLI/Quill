"""Global shortcuts registered with Windows instead of a keyboard hook."""

import logging

from PySide6.QtCore import QObject, Signal
from pynput import keyboard
from pynput.mouse import Controller as MouseController
from app.windows_hotkeys import WindowsHotkeys, shortcut_spec


logger = logging.getLogger(__name__)
_MODIFIERS = {keyboard.Key.ctrl, keyboard.Key.alt, keyboard.Key.shift, keyboard.Key.cmd}
_RESERVED = [
    frozenset(keyboard.HotKey.parse('<alt>+<f4>')),
    frozenset(keyboard.HotKey.parse('<ctrl>+<alt>+<delete>')),
    frozenset(keyboard.HotKey.parse('<ctrl>+<shift>+<esc>')),
]


def _parse_hotkey(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError('A main shortcut is required.')
    try:
        keys = keyboard.HotKey.parse(value)
    except (ValueError, TypeError) as exc:
        raise ValueError('Invalid shortcut: ' + value) from exc
    chord = frozenset(keys)
    if len(chord) != len(keys):
        raise ValueError('A shortcut cannot contain the same key twice.')
    if not chord.intersection(_MODIFIERS) or len(chord.difference(_MODIFIERS)) != 1:
        raise ValueError('Use at least one modifier and exactly one other key.')
    if chord in _RESERVED:
        raise ValueError('This shortcut is reserved by Windows.')
    return chord


def validate_hotkeys(hotkey: str, quick_hotkey: str = ''):
    """Validate both shortcut strings without changing a running listener."""
    main = _parse_hotkey(hotkey)
    if not isinstance(quick_hotkey, str):
        raise ValueError('The quick shortcut must be text.')
    quick = _parse_hotkey(quick_hotkey) if quick_hotkey else None
    main_spec = shortcut_spec(main)
    quick_spec = shortcut_spec(quick) if quick else None
    if main_spec == quick_spec:
        raise ValueError('Main and quick shortcuts must be different.')


class HotkeyManager(QObject):
    hotkey_pressed = Signal(int, int)
    quick_hotkey_pressed = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.listener = None
        self.hotkey = '<ctrl>+<space>'
        self.quick_hotkey = ''
        self.is_active = True
        self.mouse = MouseController()

    def start(self, hotkey=None, quick_hotkey=None):
        main = self.hotkey if hotkey is None else hotkey
        quick = self.quick_hotkey if quick_hotkey is None else quick_hotkey
        validate_hotkeys(main, quick)
        bindings = {_parse_hotkey(main): self._on_hotkey_activated}
        if quick:
            bindings[_parse_hotkey(quick)] = self._on_quick_hotkey_activated
        if self.is_active:
            listener = self.listener or WindowsHotkeys()
            listener.set_bindings(bindings)
            self.listener = listener
        self.hotkey, self.quick_hotkey = main, quick
        logger.info('Windows hotkeys configured: main=%s, quick=%s, active=%s', main, quick or 'disabled', self.is_active)

    def stop(self):
        if self.listener is not None:
            self.listener.stop()
            self.listener = None

    def set_hotkeys(self, hotkey=None, quick_hotkey=None):
        self.start(hotkey, quick_hotkey)

    def pause(self):
        # Release OS registrations so paused Quill does not swallow shortcuts.
        self.stop()
        self.is_active = False

    def resume(self):
        self.is_active = True
        try:
            self.start()
        except Exception:
            self.is_active = False
            raise

    def _on_hotkey_activated(self):
        if self.is_active:
            try:
                self.hotkey_pressed.emit(*self.mouse.position)
            except Exception:
                logger.exception('Error in main hotkey callback')

    def _on_quick_hotkey_activated(self):
        if self.is_active:
            try:
                self.quick_hotkey_pressed.emit(*self.mouse.position)
            except Exception:
                logger.exception('Error in quick hotkey callback')

    def is_running(self):
        return self.listener is not None and self.listener.running
