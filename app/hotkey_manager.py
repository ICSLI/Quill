"""Global shortcuts with exact chord matching and predictable listener lifetime."""

import logging
import threading
from typing import Optional

from PySide6.QtCore import QObject, Signal
from pynput import keyboard
from pynput.mouse import Controller as MouseController


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
    if main == quick:
        raise ValueError('Main and quick shortcuts must be different.')


class HotkeyManager(QObject):
    hotkey_pressed = Signal(int, int)
    quick_hotkey_pressed = Signal(int, int)

    def __init__(self):
        super().__init__()
        self.listener: Optional[keyboard.Listener] = None
        self.hotkey = '<ctrl>+<space>'
        self.quick_hotkey = ''
        self.is_active = True
        self.mouse = MouseController()
        self._pressed = set()
        self._active_chords = set()
        self._bindings = {}

    def start(self, hotkey=None, quick_hotkey=None):
        main = self.hotkey if hotkey is None else hotkey
        quick = self.quick_hotkey if quick_hotkey is None else quick_hotkey
        validate_hotkeys(main, quick)
        bindings = {_parse_hotkey(main): self._on_hotkey_activated}
        if quick:
            bindings[_parse_hotkey(quick)] = self._on_quick_hotkey_activated
        self.stop()
        self._bindings = bindings
        listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener = listener
        try:
            listener.start()
            listener.wait()
        except Exception as exc:
            self.stop()
            raise RuntimeError('Failed to start hotkey listener: ' + str(exc)) from exc
        self.hotkey, self.quick_hotkey = main, quick
        logger.info('Hotkey listener started: main=%s, quick=%s', main, quick or 'disabled')

    def stop(self):
        listener, self.listener = self.listener, None
        if listener is not None:
            listener.stop()
            if listener is not threading.current_thread() and listener.ident is not None:
                listener.join(timeout=1)
        self._pressed.clear()
        self._active_chords.clear()

    def set_hotkeys(self, hotkey=None, quick_hotkey=None):
        # Rebuild bindings while paused, too; resume must use the newly saved shortcuts.
        self.start(hotkey, quick_hotkey)

    def pause(self):
        self.is_active = False
        self._active_chords.clear()

    def resume(self):
        self.is_active = True

    def _on_press(self, key):
        listener = self.listener
        if listener is None:
            return
        self._pressed.add(listener.canonical(key))
        chord = frozenset(self._pressed)
        # Exact matching prevents Ctrl+Shift+Space from also firing Ctrl+Space.
        if self.is_active and chord in self._bindings and chord not in self._active_chords:
            self._active_chords.add(chord)
            self._bindings[chord]()

    def _on_release(self, key):
        listener = self.listener
        if listener is not None:
            self._pressed.discard(listener.canonical(key))
        # A subset chord is never triggered just by releasing an extra modifier.
        self._active_chords = {chord for chord in self._active_chords if chord.issubset(self._pressed)}

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
