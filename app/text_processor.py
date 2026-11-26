"""Copy and replace selected text without blocking the GUI event loop."""

import ctypes
from ctypes import wintypes
import logging
import sys
import threading
import time
import uuid
from typing import Optional

import pyperclip
from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot
from app.windows_input import WindowsKeyboard
from core.diagnostics import record


logger = logging.getLogger(__name__)


class _GUIThreadInfo(ctypes.Structure):
    _fields_ = [
        ('size', wintypes.DWORD), ('flags', wintypes.DWORD),
        ('active', wintypes.HWND), ('focus', wintypes.HWND),
        ('capture', wintypes.HWND), ('menu_owner', wintypes.HWND),
        ('move_size', wintypes.HWND), ('caret', wintypes.HWND), ('caret_rect', wintypes.RECT),
    ]


if sys.platform == 'win32':
    _user32 = ctypes.WinDLL('user32', use_last_error=True)
    _user32.GetForegroundWindow.restype = ctypes.c_void_p
    _user32.GetClipboardOwner.restype = wintypes.HWND
    _user32.GetClipboardSequenceNumber.restype = wintypes.DWORD
    _user32.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetClassNameW.restype = ctypes.c_int
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.POINTER(_GUIThreadInfo)]
    _user32.GetGUIThreadInfo.restype = wintypes.BOOL

_CONSOLE_CLASSES = {'consolewindowclass', 'cascadia_hosting_window_class'}


def _foreground_window():
    """Return a pointer-sized HWND; an unknown target must never receive a paste."""
    if sys.platform == 'win32':
        return _user32.GetForegroundWindow()
    return None


def _window_class(hwnd):
    name = ctypes.create_unicode_buffer(256)
    _user32.GetClassNameW(hwnd, name, len(name))
    return name.value.casefold()


def _focused_control(window):
    if window:
        thread = _user32.GetWindowThreadProcessId(window, None)
        info = _GUIThreadInfo(size=ctypes.sizeof(_GUIThreadInfo))
        if thread and _user32.GetGUIThreadInfo(thread, ctypes.byref(info)) and info.active == window:
            return info.focus
    return None


def _clipboard_sequence():
    return _user32.GetClipboardSequenceNumber()


def _window_process(hwnd):
    pid = wintypes.DWORD()
    if hwnd:
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    return pid.value


def _clipboard_owner_process():
    return _window_process(_user32.GetClipboardOwner())


def _clipboard_snapshot():
    sequence = _clipboard_sequence()
    value = pyperclip.paste()
    if sequence == _clipboard_sequence():
        return sequence, value
    return None


class TextWorker(QObject):
    text_extracted = Signal(str)
    text_replaced = Signal()
    operation_failed = Signal(str)
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.keyboard = WindowsKeyboard()
        self.operation: Optional[str] = None
        self.replacement_text = ''
        self.expected_text = ''
        self.target_window = None
        self.target_control = None
        self._clipboard_state = None
        self.sleep_duration = 0.5  # Upper bound; ordinary copies complete immediately.
        self.done = threading.Event()

    @Slot()
    def run(self):
        try:
            if self.operation == 'extract':
                self._extract()
            elif self.operation == 'replace':
                self._replace()
        finally:
            self.done.set()
            self.finished.emit()

    def _release_modifiers(self):
        self.keyboard.release_modifiers()
        time.sleep(0.03)

    def _shortcut(self, key):
        self.keyboard.shortcut(key)

    def _check_target(self):
        if not self.target_window or _foreground_window() != self.target_window:
            raise RuntimeError('The active window changed. Select the text again before retrying.')
        if _window_class(self.target_window) in _CONSOLE_CLASSES:
            raise RuntimeError('Quill does not send copy or paste shortcuts to terminal windows.')
        if self.target_control and _focused_control(self.target_window) != self.target_control:
            raise RuntimeError('The active input field changed. Return to the original field and try again.')

    def _write_clipboard(self, value, previous=None):
        if previous is not None and _clipboard_sequence() != previous[0]:
            raise RuntimeError('The clipboard changed. Select the text again before retrying.')
        pyperclip.copy(value)
        written = _clipboard_snapshot()
        if written is None or written[1] != value:
            raise RuntimeError('Could not prepare the clipboard. Please retry.')
        self._clipboard_state = written

    def _read_original_clipboard(self):
        # Reading a delayed format can itself advance the Windows sequence.
        original = _clipboard_snapshot() or _clipboard_snapshot()
        if original is None:
            raise RuntimeError('The clipboard changed. Select the text again before retrying.')
        return original

    def _restore_clipboard(self, original):
        if (original is not None and self._clipboard_state is not None
                and _clipboard_snapshot() == self._clipboard_state):
            pyperclip.copy(original[1])

    def _copy_selection(self, original=None):
        """A verified non-NUL marker distinguishes a new copy, including identical text."""
        marker = 'QUILL_CLIPBOARD_' + uuid.uuid4().hex
        self._check_target()
        self._write_clipboard(marker, original)
        self._check_target()
        self._shortcut('c')
        deadline = time.monotonic() + self.sleep_duration
        while True:
            copied = _clipboard_snapshot()
            # Copying applications can empty the clipboard before publishing text.
            # Keep waiting through that transient state, bounded by the deadline.
            if copied and copied[1] and copied[1] != marker:
                owner, source = _clipboard_owner_process(), _window_process(self.target_window)
                if _clipboard_sequence() == copied[0]:
                    if owner and source and owner != source:
                        raise RuntimeError('Another application changed the clipboard. Select the text and try again.')
                    self._clipboard_state = copied
                    self._check_target()
                    return copied[1]
            if time.monotonic() >= deadline:
                record('selection.copy_timed_out')
                return ''
            time.sleep(0.01)

    def _extract(self):
        original = None
        selected = ''
        failures = []
        try:
            self._check_target()
            self._release_modifiers()
            original = self._read_original_clipboard()
            selected = self._copy_selection(original)
        except Exception as exc:
            logger.warning('Text extraction failed: %s', exc)
            failures.append(str(exc))
        finally:
            if original is not None:
                try:
                    self._restore_clipboard(original)
                except Exception as exc:
                    logger.warning('Clipboard restoration failed: %s', exc)
                    selected = ''
                    failures.append('Could not restore the clipboard. Please retry.')
        # The GUI may immediately start another operation or copy a recovered
        # response. Finish all clipboard work before exposing either outcome.
        self.done.set()
        if failures:
            self.operation_failed.emit('\n'.join(failures))
        self.text_extracted.emit(selected)

    def _replace(self):
        original = None
        paste_attempted = False
        succeeded = False
        failures = []
        try:
            if not self.replacement_text or not self.replacement_text.strip():
                raise RuntimeError('The response is empty; the selected text was kept.')
            if not self.expected_text:
                raise RuntimeError('No original selection is available. Please select the text again.')
            self._check_target()
            self._release_modifiers()
            original = self._read_original_clipboard()
            selection = self._copy_selection(original)
            if not selection:
                raise RuntimeError('The application did not return the selected text before the copy timed out.')
            if selection != self.expected_text:
                raise RuntimeError('The selected text changed. Select it again before retrying.')
            self._check_target()
            # Preserve response whitespace: it can be meaningful in code and prose.
            self._write_clipboard(self.replacement_text, self._clipboard_state)
            self._check_target()
            if _clipboard_sequence() != self._clipboard_state[0]:
                raise RuntimeError('The clipboard changed before paste. Please retry.')
            paste_attempted = True
            self._shortcut('v')
            time.sleep(0.15)  # Avoid immediately starting another clipboard operation.
            succeeded = True
        except Exception as exc:
            logger.warning('Text replacement failed: %s', exc)
            failures.append(str(exc))
        finally:
            # SendInput cannot confirm when the destination reads the clipboard.
            # A partially delivered Ctrl+V can still paste after an error here.
            if not paste_attempted:
                try:
                    self._restore_clipboard(original)
                except Exception as exc:
                    logger.warning('Clipboard restoration failed: %s', exc)
                    failures.append('Could not restore the clipboard. Check the target before retrying.')
        self.done.set()
        if failures:
            self.operation_failed.emit('\n'.join(failures))
        elif succeeded:
            self.text_replaced.emit()


class TextProcessor(QObject):
    text_extracted = Signal(str)
    text_replaced = Signal()
    operation_failed = Signal(str)

    def __init__(self):
        super().__init__()
        self._thread: Optional[QThread] = None
        self._worker: Optional[TextWorker] = None
        self._target_window = None
        self._target_control = None
        self._selected_text = ''
        self._closed = False

    def _cleanup_previous(self, wait=False):
        if self._thread is not None:
            if self._thread.isRunning():
                if not wait and not self._worker.done.is_set():
                    return False
                self._thread.quit()
                # Never destroy a running QThread. Worker operations are bounded.
                self._thread.wait()
            self._thread.deleteLater()
            self._thread = None
            self._worker = None
        return True

    def _start_operation(self, operation, replacement_text=''):
        if self._closed or not self._cleanup_previous():
            self.operation_failed.emit('Another clipboard operation is in progress. Please retry.')
            if operation == 'extract':
                self.text_extracted.emit('')
            return
        if operation == 'extract':
            self._target_window = _foreground_window()
            self._target_control = _focused_control(self._target_window)
            self._selected_text = ''

        worker = self._worker = TextWorker()
        thread = self._thread = QThread()
        worker.operation = operation
        worker.replacement_text = replacement_text
        worker.expected_text = self._selected_text
        worker.target_window = self._target_window
        worker.target_control = self._target_control
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.text_extracted.connect(self._on_text_extracted)
        worker.text_replaced.connect(self.text_replaced)
        worker.operation_failed.connect(self.operation_failed)
        worker.finished.connect(thread.quit, Qt.ConnectionType.DirectConnection)
        worker.finished.connect(worker.deleteLater)
        thread.start()

    @Slot(str)
    def _on_text_extracted(self, text):
        self._selected_text = text
        self.text_extracted.emit(text)

    def extract_selected_text(self):
        self._start_operation('extract')

    def replace_text(self, new_text):
        self._start_operation('replace', new_text)

    def cleanup(self):
        self._closed = True
        self._cleanup_previous(wait=True)
