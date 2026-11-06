"""Clipboard and shortcut regressions without sending real keyboard input."""

import os
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from pynput import keyboard
from pynput.keyboard import _base

from app import hotkey_manager as hotkeys
from app import text_processor as text


class ClipboardTests(unittest.TestCase):
    def setUp(self):
        self.clipboard = 'original clipboard'
        self.selection = 'selected text'
        self.pastes = []
        self.patches = [
            patch.object(text, 'Controller', return_value=Mock()),
            patch.object(text, '_foreground_window', return_value=123),
            patch.object(text.pyperclip, 'copy', side_effect=self.copy),
            patch.object(text.pyperclip, 'paste', side_effect=lambda: self.clipboard),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.worker = text.TextWorker()
        self.worker.target_window = 123
        self.worker.expected_text = self.selection
        self.worker.replacement_text = 'replacement  \n'
        self.worker.sleep_duration = 0.01
        self.worker._release_modifiers = Mock()
        self.worker._shortcut = Mock(side_effect=self.shortcut)
        self.extracted, self.errors, self.replaced = [], [], []
        self.worker.text_extracted.connect(self.extracted.append)
        self.worker.operation_failed.connect(self.errors.append)
        self.worker.text_replaced.connect(lambda: self.replaced.append(True))

    def copy(self, value):
        self.clipboard = value

    def shortcut(self, key):
        if key == 'c' and self.selection is not None:
            self.clipboard = self.selection
        elif key == 'v':
            self.pastes.append(self.clipboard)

    def test_identical_selection_and_original_clipboard_is_valid(self):
        self.clipboard = self.selection
        self.worker._extract()
        self.assertEqual(self.extracted, [self.selection])
        self.assertEqual(self.clipboard, self.selection)
        self.assertFalse(self.errors)

    def test_no_selection_restores_clipboard(self):
        self.selection = None
        self.worker._extract()
        self.assertEqual(self.extracted, [''])
        self.assertEqual(self.clipboard, 'original clipboard')

    def test_failed_marker_verification_does_not_copy_stale_text(self):
        def failed_marker(value):
            if not value.startswith('QUILL_CLIPBOARD_'):
                self.clipboard = value
        text.pyperclip.copy.side_effect = failed_marker
        self.worker._extract()
        self.assertEqual(self.extracted, [''])
        self.assertTrue(self.errors)
        self.worker._shortcut.assert_not_called()
        self.assertEqual(self.clipboard, 'original clipboard')

    def test_keyboard_failure_restores_clipboard(self):
        self.worker._shortcut.side_effect = RuntimeError('keyboard unavailable')
        self.worker._extract()
        self.assertEqual(self.clipboard, 'original clipboard')
        self.assertEqual(self.extracted, [''])
        self.assertTrue(self.errors)

    def test_restore_failure_does_not_deliver_a_successful_extraction(self):
        def copy(value):
            if value == 'original clipboard':
                raise RuntimeError('clipboard busy')
            self.copy(value)
        text.pyperclip.copy.side_effect = copy
        self.worker._extract()
        self.assertEqual(self.extracted, [''])
        self.assertTrue(self.errors)

    def test_replacement_preserves_whitespace_and_restores_clipboard(self):
        self.worker._replace()
        self.assertEqual(self.pastes, ['replacement  \n'])
        self.assertEqual(self.clipboard, 'original clipboard')
        self.assertEqual(self.replaced, [True])
        self.assertFalse(self.errors)

    def test_changed_selection_is_never_overwritten(self):
        self.selection = 'newly selected text'
        self.worker._replace()
        self.assertFalse(self.pastes)
        self.assertFalse(self.replaced)
        self.assertTrue(self.errors)
        self.assertEqual(self.clipboard, 'original clipboard')

    def test_changed_window_is_never_pasted_into(self):
        text._foreground_window.return_value = 456
        self.worker._replace()
        self.assertFalse(self.pastes)
        text.pyperclip.copy.assert_not_called()
        self.assertTrue(self.errors)

    def test_window_change_during_selection_verification_aborts(self):
        def shortcut(key):
            self.shortcut(key)
            text._foreground_window.return_value = 456
        self.worker._shortcut.side_effect = shortcut
        self.worker._replace()
        self.assertFalse(self.pastes)
        self.assertEqual(self.clipboard, 'original clipboard')
        self.assertTrue(self.errors)

    def test_empty_response_keeps_selection(self):
        self.worker.replacement_text = '  \n'
        self.worker._replace()
        self.assertFalse(self.pastes)
        text.pyperclip.copy.assert_not_called()
        self.assertTrue(self.errors)

    def test_clipboard_update_after_paste_is_preserved(self):
        def shortcut(key):
            self.shortcut(key)
            if key == 'v':
                self.clipboard = 'new user clipboard'
        self.worker._shortcut.side_effect = shortcut
        self.worker._replace()
        self.assertEqual(self.clipboard, 'new user clipboard')
        self.assertEqual(self.replaced, [True])

    def test_finished_worker_can_be_cleaned_up_and_reused(self):
        app = QApplication.instance() or QApplication([])
        processor = text.TextProcessor()
        received = []
        processor.text_extracted.connect(received.append)
        with patch.object(text.TextWorker, '_release_modifiers'), patch.object(
            text.TextWorker, '_shortcut', side_effect=self.shortcut
        ):
            for _ in range(3):
                processor.extract_selected_text()
                deadline = time.monotonic() + 2
                while processor._thread.isRunning() and time.monotonic() < deadline:
                    app.processEvents()
                    time.sleep(0.001)
                app.processEvents()
                self.assertFalse(processor._thread.isRunning())
            processor.cleanup()
        self.assertEqual(received, [self.selection] * 3)
        self.assertIsNone(processor._thread)


class ShortcutTests(unittest.TestCase):
    def setUp(self):
        with patch.object(hotkeys, 'MouseController'):
            self.manager = hotkeys.HotkeyManager()
        self.manager.listener = Mock()
        self.manager.listener.canonical.side_effect = lambda value: _base.Listener.canonical(None, value)
        self.main, self.quick = Mock(), Mock()
        self.manager._bindings = {
            frozenset(keyboard.HotKey.parse('<ctrl>+<space>')): self.main,
            frozenset(keyboard.HotKey.parse('<ctrl>+<shift>+<space>')): self.quick,
        }

    def press(self, *keys):
        for key in keys:
            self.manager._on_press(key)

    def test_quick_chord_does_not_trigger_main(self):
        self.press(keyboard.Key.ctrl, keyboard.Key.shift, keyboard.Key.space)
        self.quick.assert_called_once()
        self.main.assert_not_called()
        self.manager._on_release(keyboard.Key.shift)
        self.main.assert_not_called()

    def test_key_repeat_is_suppressed_until_release(self):
        self.press(keyboard.Key.ctrl, keyboard.Key.space, keyboard.Key.space)
        self.main.assert_called_once()
        self.manager._on_release(keyboard.Key.space)
        self.press(keyboard.Key.space)
        self.assertEqual(self.main.call_count, 2)

    def test_paused_listener_ignores_shortcuts(self):
        self.manager.pause()
        self.press(keyboard.Key.ctrl, keyboard.Key.space)
        self.main.assert_not_called()

    def test_reordered_duplicate_chords_are_rejected(self):
        with self.assertRaises(ValueError):
            hotkeys.validate_hotkeys('<ctrl>+<space>', '<space>+<ctrl>')

    def test_malformed_and_reserved_shortcuts_are_rejected(self):
        for value in ('', 'q', '<ctrl>+<ctrl>+q', '<ctrl>+<shift>', '<f4>+<alt>',
                      '<delete>+<alt>+<ctrl>', '<shift>+<esc>+<ctrl>'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                hotkeys.validate_hotkeys(value)

    def test_invalid_settings_leave_current_listener_untouched(self):
        listener = self.manager.listener
        with self.assertRaises(ValueError):
            self.manager.set_hotkeys('invalid shortcut')
        self.assertIs(self.manager.listener, listener)
        listener.stop.assert_not_called()

    def test_settings_update_while_paused_rebuilds_listener(self):
        self.manager.pause()
        self.manager.listener.ident = None
        with patch.object(hotkeys.keyboard, 'Listener') as factory:
            factory.return_value.ident = None
            self.manager.set_hotkeys('<alt>+q', '<alt>+w')
            self.assertEqual(self.manager.hotkey, '<alt>+q')
            self.assertFalse(self.manager.is_active)
            factory.return_value.start.assert_called_once()
            self.assertIn(frozenset(keyboard.HotKey.parse('<alt>+w')), self.manager._bindings)
            self.manager.stop()


if __name__ == '__main__':
    unittest.main()
