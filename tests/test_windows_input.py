"""Validate native keyboard input with no real SendInput calls."""

import ctypes
import unittest
from unittest.mock import Mock

from app import windows_input as native


class WindowsInputTests(unittest.TestCase):
    def setUp(self):
        self.api = Mock()
        self.batches = []
        self.results = []
        def send(count, inputs, size):
            self.assertEqual(size, ctypes.sizeof(native.INPUT))
            self.assertTrue(all(entry.type == native.INPUT_KEYBOARD for entry in inputs))
            self.batches.append([(entry.ki.wVk, entry.ki.dwFlags) for entry in inputs])
            return self.results.pop(0) if self.results else count
        self.api.SendInput.side_effect = send
        self.keyboard = native.WindowsKeyboard(api=self.api)

    def test_windows_input_layout_for_32_and_64_bit_pointers(self):
        for pointer, size, offset in ((ctypes.c_uint32, 28, 4), (ctypes.c_uint64, 40, 8)):
            with self.subTest(pointer_bits=ctypes.sizeof(pointer) * 8):
                structure = native._input_type(pointer)
                self.assertEqual(ctypes.sizeof(structure), size)
                self.assertEqual(structure.value.offset, offset)
        self.assertEqual(ctypes.sizeof(native.INPUT), 40 if ctypes.sizeof(ctypes.c_void_p) == 8 else 28)

    def test_copy_and_paste_ordering(self):
        for letter in ('c', 'v'):
            with self.subTest(letter=letter):
                self.keyboard.shortcut(letter)
                vk = ord(letter.upper())
                self.assertEqual(self.batches[-1], [(0x11, 0), (vk, 0), (vk, 2), (0x11, 2)])

    def test_zero_or_partial_input_is_an_error_and_attempts_key_up(self):
        for sent in range(4):
            with self.subTest(accepted=sent):
                self.batches.clear()
                self.results = [sent, 2]
                with self.assertRaisesRegex(RuntimeError, f'Windows accepted {sent} of 4'):
                    self.keyboard.shortcut('v')
                self.assertEqual(self.batches[-1], [(ord('V'), 2), (0x11, 2)])

    def test_failed_key_up_keeps_the_original_input_error(self):
        self.results = [1, 0]
        with self.assertRaisesRegex(RuntimeError, 'Windows accepted 1 of 4'):
            self.keyboard.shortcut('c')
        self.assertEqual(len(self.batches), 2)

    def test_releases_left_and_right_modifiers_with_extended_flags(self):
        self.keyboard.release_modifiers()
        self.assertEqual(self.batches, [[(0xA2, 2), (0xA3, 3), (0xA4, 2), (0xA5, 3),
                                        (0xA0, 2), (0xA1, 2), (0x5B, 3), (0x5C, 3)]])

    def test_modifier_release_failure_is_reported(self):
        self.results = [0]
        with self.assertRaisesRegex(RuntimeError, 'Windows accepted 0 of 8'):
            self.keyboard.release_modifiers()

    def test_unsupported_shortcut_sends_nothing(self):
        with self.assertRaises(ValueError):
            self.keyboard.shortcut('x')
        self.api.SendInput.assert_not_called()


if __name__ == '__main__':
    unittest.main()
