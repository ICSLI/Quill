"""Windows registration and message dispatch, without injecting key input."""

import ctypes
from ctypes import wintypes
import os
import subprocess
import sys
import textwrap
import unittest
from unittest.mock import Mock, patch

from pynput import keyboard
from app import windows_hotkeys as native


def chord(value):
    return frozenset(keyboard.HotKey.parse(value))


class WindowsHotkeyTests(unittest.TestCase):
    def setUp(self):
        self.app, self.api = Mock(), Mock()
        self.api.RegisterHotKey.return_value = True
        self.api.VkKeyScanW.side_effect = lambda char: ord(char.upper()) if char.isalpha() else 0x1bf
        with patch.object(native.QCoreApplication, 'instance', return_value=self.app), patch.object(
            native, '_user32', return_value=self.api
        ):
            self.backend = native.WindowsHotkeys()
        self.addCleanup(self.backend.stop)
        self.main, self.quick = Mock(), Mock()

    def dispatch(self, message, identifier, event_type=b'windows_dispatcher_MSG'):
        msg = wintypes.MSG()
        msg.message, msg.wParam = message, identifier
        return self.backend.nativeEventFilter(event_type, ctypes.addressof(msg))

    def test_registers_norepeat_and_routes_exact_chords(self):
        self.backend.set_bindings({chord('<ctrl>+<space>'): self.main,
                                   chord('<ctrl>+<shift>+<space>'): self.quick})
        specs = [(call.args[2], call.args[3]) for call in self.api.RegisterHotKey.call_args_list]
        self.assertEqual(specs, [(2 | native.MOD_NOREPEAT, 32), (6 | native.MOD_NOREPEAT, 32)])
        identifier = self.backend._registrations[(6, 32)]
        self.assertEqual(self.dispatch(native.WM_HOTKEY, identifier), (True, 0))
        self.quick.assert_called_once()
        self.main.assert_not_called()

    def test_ordinary_key_release_order_cannot_poison_later_hotkey(self):
        self.backend.set_bindings({chord('<ctrl>+<space>'): self.main})
        # Control+C, then release Control before C, formerly left a stale character.
        for message, key in [(0x100, 17), (0x100, 67), (0x101, 17), (0x101, 67)]:
            self.assertEqual(self.dispatch(message, key), (False, 0))
        self.dispatch(native.WM_HOTKEY, self.backend._registrations[(2, 32)])
        self.main.assert_called_once()

    def test_failed_update_keeps_existing_hotkey_and_rolls_back_new_ones(self):
        self.backend.set_bindings({chord('<ctrl>+<space>'): self.main})
        original = dict(self.backend._registrations)
        self.api.RegisterHotKey.side_effect = [True, False]
        with self.assertRaisesRegex(RuntimeError, 'Windows could not register'):
            self.backend.set_bindings({chord('<alt>+q'): Mock(), chord('<alt>+w'): Mock()})
        self.assertEqual(self.backend._registrations, original)
        self.assertEqual(self.api.UnregisterHotKey.call_count, 1)
        self.dispatch(native.WM_HOTKEY, original[(2, 32)])
        self.main.assert_called_once()

    def test_first_registration_failure_removes_filter(self):
        self.api.RegisterHotKey.return_value = False
        with self.assertRaises(RuntimeError):
            self.backend.set_bindings({chord('<ctrl>+<space>'): self.main})
        self.assertFalse(self.backend.running)
        self.app.removeNativeEventFilter.assert_called_once_with(self.backend)

    def test_binding_swap_reuses_registrations(self):
        self.backend.set_bindings({chord('<ctrl>+<space>'): self.main,
                                   chord('<ctrl>+<shift>+<space>'): self.quick})
        self.api.RegisterHotKey.reset_mock()
        self.backend.set_bindings({chord('<ctrl>+<space>'): self.quick,
                                   chord('<ctrl>+<shift>+<space>'): self.main})
        self.api.RegisterHotKey.assert_not_called()
        self.dispatch(native.WM_HOTKEY, self.backend._registrations[(2, 32)])
        self.quick.assert_called_once()

    def test_stop_releases_os_registration_and_ignores_queued_messages(self):
        self.backend.set_bindings({chord('<ctrl>+<space>'): self.main})
        identifier = self.backend._registrations[(2, 32)]
        self.backend.stop()
        self.backend.stop()
        self.api.UnregisterHotKey.assert_called_once_with(None, identifier)
        self.assertEqual(self.dispatch(native.WM_HOTKEY, identifier), (False, 0))
        self.main.assert_not_called()

    def test_printable_key_mapping_and_equivalent_chord_detection(self):
        self.assertEqual(native.shortcut_spec(chord('<ctrl>+a'), self.api), (2, 65))
        self.assertEqual(native.shortcut_spec(chord('<ctrl>+?'), self.api), (6, 0xbf))
        with self.assertRaises(ValueError):
            self.backend.set_bindings({chord('<ctrl>+a'): self.main, chord('<ctrl>+<65>'): self.quick})
        self.api.RegisterHotKey.assert_not_called()

    def test_unmappable_characters_leave_existing_registration_untouched(self):
        self.backend.set_bindings({chord('<ctrl>+<space>'): self.main})
        before = dict(self.backend._registrations)
        self.api.VkKeyScanW.return_value = -1
        self.api.VkKeyScanW.side_effect = None
        with self.assertRaises(ValueError):
            self.backend.set_bindings({chord('<ctrl>+a'): self.quick})
        self.assertEqual(self.backend._registrations, before)
        self.api.VkKeyScanW.side_effect = ctypes.ArgumentError('Unsupported character')
        with self.assertRaises(ValueError):
            self.backend.set_bindings({chord('<ctrl>+a'): self.quick})
        self.assertEqual(self.backend._registrations, before)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows native dispatch')
    def test_real_windows_registration_before_event_loop_and_cleanup(self):
        script = textwrap.dedent('''
            import ctypes
            from ctypes import wintypes
            from PySide6.QtCore import QCoreApplication, QTimer
            from pynput import keyboard
            from app.windows_hotkeys import WindowsHotkeys, WM_HOTKEY
            app = QCoreApplication([])
            observed = []
            backend = WindowsHotkeys()
            keys = frozenset(keyboard.HotKey.parse('<ctrl>+<alt>+<shift>+<135>'))
            def received():
                observed.append(True)
                app.quit()
            backend.set_bindings({keys: received})
            contender = WindowsHotkeys()
            try:
                contender.set_bindings({keys: lambda: None})
            except RuntimeError:
                assert not contender.running
            else:
                raise AssertionError('Windows allowed a duplicate shortcut registration.')
            identifier = next(iter(backend._callbacks))
            user32 = ctypes.WinDLL('user32', use_last_error=True)
            user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
            thread = ctypes.windll.kernel32.GetCurrentThreadId()
            QTimer.singleShot(0, lambda: user32.PostThreadMessageW(thread, WM_HOTKEY, identifier, 7 | (135 << 16)))
            QTimer.singleShot(2000, app.quit)
            app.exec()
            backend.stop()
            assert observed == [True], observed
            # A fresh manager must be able to register immediately after cleanup.
            contender.set_bindings({keys: lambda: None})
            contender.stop()
        ''')
        result = subprocess.run([sys.executable, '-c', script], capture_output=True,
                                text=True, timeout=10, env=dict(os.environ))
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
