"""Copy and replace selected text without blocking the GUI event loop."""

import ctypes
import logging
import sys
import threading
import time
import uuid
from typing import Optional

import pyperclip
from pynput.keyboard import Controller, Key
from PySide6.QtCore import QObject, QThread, Qt, Signal, Slot


logger = logging.getLogger(__name__)

if sys.platform == 'win32':
    _user32 = ctypes.WinDLL('user32', use_last_error=True)
    _user32.GetForegroundWindow.restype = ctypes.c_void_p


def _foreground_window():
    """Return a pointer-sized HWND; an unknown target must never receive a paste."""
    if sys.platform == 'win32':
        return _user32.GetForegroundWindow()
    return None


class TextWorker(QObject):
    text_extracted = Signal(str)
    text_replaced = Signal()
    operation_failed = Signal(str)
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.keyboard = Controller()
        self.operation: Optional[str] = None
        self.replacement_text = ''
        self.expected_text = ''
        self.target_window = None
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
        for key in (Key.ctrl, Key.alt, Key.shift, Key.cmd):
            self.keyboard.release(key)
        time.sleep(0.03)

    def _shortcut(self, key):
        with self.keyboard.pressed(Key.ctrl):
            self.keyboard.press(key)
            self.keyboard.release(key)

    def _check_target(self):
        if not self.target_window or _foreground_window() != self.target_window:
            raise RuntimeError('The active window changed. Select the text again before retrying.')

    def _copy_selection(self):
        """A verified non-NUL marker distinguishes a new copy, including identical text."""
        marker = 'QUILL_CLIPBOARD_' + uuid.uuid4().hex
        pyperclip.copy(marker)
        if pyperclip.paste() != marker:
            raise RuntimeError('Could not prepare the clipboard. Please retry.')
        self._check_target()
        self._shortcut('c')
        deadline = time.monotonic() + self.sleep_duration
        while True:
            value = pyperclip.paste()
            if value != marker:
                self._check_target()
                return value
            if time.monotonic() >= deadline:
                return ''
            time.sleep(0.01)

    def _extract(self):
        original = None
        selected = ''
        try:
            self._check_target()
            self._release_modifiers()
            original = pyperclip.paste()
            selected = self._copy_selection()
        except Exception as exc:
            logger.warning('Text extraction failed: %s', exc)
            self.operation_failed.emit(str(exc))
        finally:
            if original is not None:
                try:
                    pyperclip.copy(original)
                except Exception as exc:
                    logger.warning('Clipboard restoration failed: %s', exc)
                    selected = ''
                    self.operation_failed.emit('Could not restore the clipboard. Please retry.')
            self.text_extracted.emit(selected)

    def _replace(self):
        original = None
        replacement_written = False
        succeeded = False
        try:
            if not self.replacement_text or not self.replacement_text.strip():
                raise RuntimeError('The response is empty; the selected text was kept.')
            if not self.expected_text:
                raise RuntimeError('No original selection is available. Please select the text again.')
            self._check_target()
            self._release_modifiers()
            original = pyperclip.paste()
            if self._copy_selection() != self.expected_text:
                raise RuntimeError('The selected text changed. Select it again before retrying.')
            self._check_target()
            # Preserve response whitespace: it can be meaningful in code and prose.
            pyperclip.copy(self.replacement_text)
            replacement_written = True
            if pyperclip.paste() != self.replacement_text:
                raise RuntimeError('Could not copy the response to the clipboard. Please retry.')
            self._check_target()
            self._shortcut('v')
            time.sleep(0.15)  # Give the receiving application time to consume Ctrl+V.
            succeeded = True
        except Exception as exc:
            logger.warning('Text replacement failed: %s', exc)
            self.operation_failed.emit(str(exc))
        finally:
            if original is not None:
                try:
                    # Do not overwrite a clipboard update made after our paste.
                    if not replacement_written or pyperclip.paste() == self.replacement_text:
                        pyperclip.copy(original)
                except Exception as exc:
                    logger.warning('Clipboard restoration failed: %s', exc)
                    self.operation_failed.emit('Could not restore the clipboard. Please retry.')
            if succeeded:
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
            self._selected_text = ''

        worker = self._worker = TextWorker()
        thread = self._thread = QThread()
        worker.operation = operation
        worker.replacement_text = replacement_text
        worker.expected_text = self._selected_text
        worker.target_window = self._target_window
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
