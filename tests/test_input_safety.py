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
        self.sequence = 3
        self.selection = 'selected text'
        self.pastes = []
        self.patches = [
            patch.object(text, 'WindowsKeyboard', return_value=Mock()),
            patch.object(text, '_foreground_window', return_value=123),
            patch.object(text, '_focused_control', return_value=321),
            patch.object(text, '_window_class', return_value='notepad'),
            patch.object(text, '_clipboard_sequence', side_effect=lambda: self.sequence),
            patch.object(text, '_window_process', return_value=17),
            patch.object(text, '_clipboard_owner_process', return_value=17),
            patch.object(text.pyperclip, 'copy', side_effect=self.copy),
            patch.object(text.pyperclip, 'paste', side_effect=lambda: self.clipboard),
        ]
        for item in self.patches:
            item.start()
            self.addCleanup(item.stop)
        self.worker = text.TextWorker()
        self.worker.target_window = 123
        self.worker.target_control = 321
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
        self.sequence += 1

    def shortcut(self, key):
        if key == 'c' and self.selection is not None:
            self.copy(self.selection)
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

    def test_copy_waits_for_text_after_transient_empty_clipboard(self):
        with patch.object(text.uuid, 'uuid4', return_value=Mock(hex='test')):
            text.pyperclip.paste.side_effect = ['QUILL_CLIPBOARD_test', '', self.selection]
            self.assertEqual(self.worker._copy_selection(), self.selection)
        self.assertEqual(text.pyperclip.paste.call_count, 3)

    def test_modifier_release_includes_both_sides_before_copying(self):
        with patch.object(text.time, 'sleep'):
            text.TextWorker._release_modifiers(self.worker)
        self.worker.keyboard.release_modifiers.assert_called_once()

    def test_rejected_paste_reports_failure_and_keeps_response_available(self):
        from app.windows_input import WindowsKeyboard
        api = Mock()
        api.SendInput.return_value = 0
        self.worker.keyboard = WindowsKeyboard(api=api)
        self.worker._copy_selection = Mock(return_value=self.selection)
        self.worker._shortcut = lambda key: text.TextWorker._shortcut(self.worker, key)
        self.worker._replace()
        self.assertFalse(self.replaced)
        self.assertTrue(self.errors)
        self.assertEqual(self.worker.replacement_text, 'replacement  \n')
        self.assertEqual(self.clipboard, self.worker.replacement_text)

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

    def test_extraction_failure_callback_runs_after_clipboard_cleanup(self):
        self.worker._shortcut.side_effect = RuntimeError('keyboard unavailable')
        observed = []
        def recover(message):
            observed.append((self.clipboard, self.worker.done.is_set()))
            self.clipboard = 'new clipboard from error callback'
        self.worker.operation_failed.connect(recover)
        self.worker._extract()
        self.assertEqual(observed, [('original clipboard', True)])
        self.assertEqual(self.clipboard, 'new clipboard from error callback')
        self.assertEqual(self.extracted, [''])
        self.assertEqual(len(self.errors), 1)

    def test_replacement_failure_callback_cannot_be_overwritten_by_restoration(self):
        self.selection = 'changed selection'
        observed = []
        def recover(message):
            observed.append((self.clipboard, self.worker.done.is_set()))
            self.clipboard = self.worker.replacement_text
        self.worker.operation_failed.connect(recover)
        self.worker._replace()
        self.assertEqual(observed, [('original clipboard', True)])
        self.assertEqual(self.clipboard, self.worker.replacement_text)
        self.assertEqual(len(self.errors), 1)
        self.assertFalse(self.replaced)

    def test_copy_and_restore_errors_emit_one_extraction_failure(self):
        self.worker._shortcut.side_effect = RuntimeError('keyboard unavailable')
        def copy(value):
            if value == 'original clipboard':
                raise RuntimeError('clipboard busy')
            self.copy(value)
        text.pyperclip.copy.side_effect = copy
        self.worker._extract()
        self.assertEqual(len(self.errors), 1)
        self.assertIn('keyboard unavailable', self.errors[0])
        self.assertIn('Could not restore', self.errors[0])
        self.assertEqual(self.extracted, [''])

    def test_selection_and_restore_errors_emit_one_replacement_failure(self):
        self.selection = 'changed selection'
        def copy(value):
            if value == 'original clipboard':
                raise RuntimeError('clipboard busy')
            self.copy(value)
        text.pyperclip.copy.side_effect = copy
        self.worker._replace()
        self.assertEqual(len(self.errors), 1)
        self.assertIn('selected text changed', self.errors[0])
        self.assertIn('Could not restore', self.errors[0])
        self.assertFalse(self.replaced)

    def test_successfully_queued_paste_does_not_restore_the_previous_clipboard(self):
        def copy(value):
            if value == 'original clipboard':
                raise RuntimeError('clipboard busy')
            self.copy(value)
        text.pyperclip.copy.side_effect = copy
        self.worker._replace()
        self.assertEqual(self.pastes, [self.worker.replacement_text])
        self.assertFalse(self.errors)
        self.assertEqual(self.replaced, [True])
        self.assertEqual(self.clipboard, self.worker.replacement_text)
        self.assertEqual(self.worker.replacement_text, 'replacement  \n')

    def test_restore_failure_does_not_deliver_a_successful_extraction(self):
        def copy(value):
            if value == 'original clipboard':
                raise RuntimeError('clipboard busy')
            self.copy(value)
        text.pyperclip.copy.side_effect = copy
        self.worker._extract()
        self.assertEqual(self.extracted, [''])
        self.assertTrue(self.errors)

    def test_replacement_preserves_whitespace_and_leaves_response_for_delayed_paste(self):
        self.worker._replace()
        self.assertEqual(self.pastes, ['replacement  \n'])
        self.assertEqual(self.clipboard, 'replacement  \n')
        self.assertEqual(self.replaced, [True])
        self.assertFalse(self.errors)

    def test_extraction_preserves_a_new_clipboard_write_even_if_text_matches(self):
        restore = self.worker._restore_clipboard
        def copy_again_before_restore(original):
            self.copy(self.selection)
            restore(original)
        self.worker._restore_clipboard = copy_again_before_restore
        self.worker._extract()
        self.assertEqual(self.extracted, [self.selection])
        self.assertEqual(self.clipboard, self.selection)
        text.pyperclip.copy.assert_called_once()

    def test_copy_from_another_clipboard_owner_is_not_used_as_selection(self):
        text._clipboard_owner_process.return_value = 99
        self.worker._extract()
        self.assertEqual(self.extracted, [''])
        self.assertIn('Another application', self.errors[0])
        self.assertEqual(self.clipboard, self.selection)

    def test_text_selection_from_terminal_is_blocked_before_sending_keys(self):
        text._window_class.return_value = 'cascadia_hosting_window_class'
        self.worker._extract()
        self.worker._shortcut.assert_not_called()
        self.worker._release_modifiers.assert_not_called()
        text.pyperclip.copy.assert_not_called()
        self.assertIn('terminal windows', self.errors[0])

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

    def test_same_window_with_another_focused_control_is_not_modified(self):
        text._focused_control.return_value = 322
        self.worker._replace()
        text.pyperclip.copy.assert_not_called()
        self.worker._shortcut.assert_not_called()
        self.assertIn('input field changed', self.errors[0])

    def test_copy_can_succeed_when_native_control_is_unavailable(self):
        text._focused_control.return_value = None
        self.worker.target_control = None
        self.worker._extract()
        self.assertEqual(self.extracted, [self.selection])

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

    def test_extraction_callback_can_immediately_start_replacement(self):
        app = QApplication.instance() or QApplication([])
        processor = text.TextProcessor()
        errors, replaced = [], []
        processor.operation_failed.connect(errors.append)
        processor.text_extracted.connect(lambda selected: processor.replace_text('replacement'))
        processor.text_replaced.connect(lambda: replaced.append(True))
        try:
            with patch.object(text.TextWorker, '_release_modifiers'), patch.object(
                text.TextWorker, '_shortcut', side_effect=self.shortcut
            ):
                processor.extract_selected_text()
                deadline = time.monotonic() + 2
                while not replaced and not errors and time.monotonic() < deadline:
                    app.processEvents()
                    time.sleep(0.001)
                self.assertEqual(errors, [])
                self.assertEqual(replaced, [True])
                self.assertEqual(self.pastes, ['replacement'])
        finally:
            processor.cleanup()


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

    def test_internal_copy_and_paste_shortcuts_are_rejected_in_both_bindings(self):
        for shortcut in ('<ctrl>+c', '<ctrl>+v', '<ctrl>+C', '<ctrl>+V',
                         '<ctrl>+<67>', '<ctrl>+<86>', '<67>+<ctrl>', '<86>+<ctrl>'):
            for main, quick in ((shortcut, ''), ('<ctrl>+<space>', shortcut)):
                with self.subTest(main=main, quick=quick), self.assertRaisesRegex(ValueError, 'Ctrl\\+C and Ctrl\\+V'):
                    hotkeys.validate_hotkeys(main, quick)

    def test_clipboard_shortcuts_use_the_resolved_keyboard_layout(self):
        with patch('app.windows_hotkeys._user32') as api:
            api.return_value.VkKeyScanW.return_value = ord('C')
            with self.assertRaisesRegex(ValueError, 'Ctrl\\+C and Ctrl\\+V'):
                hotkeys.validate_hotkeys('<ctrl>+x')

    def test_additional_modifiers_do_not_conflict_with_internal_shortcuts(self):
        hotkeys.validate_hotkeys('<ctrl>+<shift>+c', '<ctrl>+<alt>+v')

    def test_internal_shortcut_rejection_keeps_current_registration(self):
        self.manager.start()
        self.backend.set_bindings.reset_mock()
        for main, quick in (('<ctrl>+c', ''), ('<ctrl>+<space>', '<ctrl>+<86>')):
            with self.subTest(main=main, quick=quick), self.assertRaises(ValueError):
                self.manager.set_hotkeys(main, quick)
        self.backend.set_bindings.assert_not_called()
        self.backend.stop.assert_not_called()

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
