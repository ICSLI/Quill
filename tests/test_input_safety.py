"""Clipboard and shortcut regressions without sending real keyboard input."""

import os
import time
import unittest
from unittest.mock import Mock, patch

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PySide6.QtWidgets import QApplication
from pynput import keyboard

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
        self.backend = Mock()
        self.factory = patch.object(hotkeys, 'WindowsHotkeys', return_value=self.backend)
        self.factory.start()
        self.addCleanup(self.factory.stop)

    def test_main_and_quick_have_separate_callbacks(self):
        self.manager.start('<ctrl>+<space>', '<ctrl>+<shift>+<space>')
        main, quick = [], []
        self.manager.mouse.position = (10, 20)
        self.manager.hotkey_pressed.connect(lambda x, y: main.append((x, y)))
        self.manager.quick_hotkey_pressed.connect(lambda x, y: quick.append((x, y)))
        bindings = self.backend.set_bindings.call_args.args[0]
        bindings[frozenset(keyboard.HotKey.parse('<ctrl>+<shift>+<space>'))]()
        self.assertEqual(quick, [(10, 20)])
        self.assertFalse(main)

    def test_pausing_releases_shortcut_and_resume_uses_updated_settings(self):
        self.manager.start()
        self.manager.pause()
        self.backend.stop.assert_called_once()
        self.assertFalse(self.manager.is_active)
        self.backend.set_bindings.reset_mock()
        self.manager.set_hotkeys('<alt>+q', '<alt>+w')
        self.backend.set_bindings.assert_not_called()
        self.manager.resume()
        bindings = self.backend.set_bindings.call_args.args[0]
        self.assertIn(frozenset(keyboard.HotKey.parse('<alt>+w')), bindings)
        self.assertTrue(self.manager.is_active)

    def test_resume_failure_remains_paused(self):
        self.manager.pause()
        self.backend.set_bindings.side_effect = RuntimeError('Shortcut busy')
        with self.assertRaises(RuntimeError):
            self.manager.resume()
        self.assertFalse(self.manager.is_active)

    def test_startup_registration_failure_is_reported(self):
        self.backend.set_bindings.side_effect = RuntimeError('Shortcut busy')
        with self.assertRaisesRegex(RuntimeError, 'Shortcut busy'):
            self.manager.start()
        self.assertFalse(self.manager.is_running())

    def test_reordered_duplicate_chords_are_rejected(self):
        with self.assertRaises(ValueError):
            hotkeys.validate_hotkeys('<ctrl>+<space>', '<space>+<ctrl>')

    def test_equivalent_windows_key_codes_are_rejected(self):
        with self.assertRaises(ValueError):
            hotkeys.validate_hotkeys('<ctrl>+a', '<ctrl>+<65>')

    def test_windows_invalid_virtual_key_is_rejected_even_while_paused(self):
        self.manager.pause()
        for shortcut in ('<ctrl>+<999>', '<ctrl>+<f12>'):
            with self.subTest(shortcut=shortcut), self.assertRaises(ValueError):
                self.manager.set_hotkeys(shortcut, '')

    def test_malformed_and_reserved_shortcuts_are_rejected(self):
        for value in ('', 'q', '<ctrl>+<ctrl>+q', '<ctrl>+<shift>', '<f4>+<alt>',
                      '<delete>+<alt>+<ctrl>', '<shift>+<esc>+<ctrl>'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                hotkeys.validate_hotkeys(value)

    def test_invalid_settings_leave_current_registration_untouched(self):
        self.manager.start()
        self.backend.set_bindings.reset_mock()
        with self.assertRaises(ValueError):
            self.manager.set_hotkeys('invalid shortcut')
        self.assertIs(self.manager.listener, self.backend)
        self.backend.set_bindings.assert_not_called()
        self.backend.stop.assert_not_called()


if __name__ == '__main__':
    unittest.main()
