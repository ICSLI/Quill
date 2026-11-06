"""Regression tests for settings transactions and popup submission."""
import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QMessageBox
from core.config_manager import ConfigManager
from core.prompt_manager import PromptManager
from ui.settings_window import SettingsWindow
from ui.popup_window import PopupWindow
from ui.onboarding_window import OnboardingWindow
from app.tray_manager import TrayManager


class UiQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.config = ConfigManager(str(Path(self.tmp.name) / "config.json"))
        self.config._config = deepcopy(ConfigManager.DEFAULT_CONFIG)
        self.config.save()
        self.prompts = PromptManager(user_prompts_path=str(Path(self.tmp.name) / "prompts.json"))
        for method in ("warning", "critical", "information"):
            patched = patch.object(QMessageBox, method, return_value=QMessageBox.StandardButton.Ok)
            patched.start()
            self.addCleanup(patched.stop)
        self.window = SettingsWindow(self.config, self.config.crypto, self.prompts)
        self.addCleanup(self.window.close)

    def test_invalid_hotkey_leaves_config_and_prompts_unchanged(self):
        before = self.config.get_all()
        prompts_before = deepcopy(self.prompts.prompts)
        disk_before = self.config.config_path.read_bytes()
        self.window.input_base_url.setText("https://example.com/v1")
        self.window.prompt_name_edit.setText("Changed name")
        self.window.input_hotkey.setText("")
        self.window._on_save()
        self.assertEqual(before, self.config.get_all())
        self.assertEqual(prompts_before, self.prompts.prompts)
        self.assertEqual(disk_before, self.config.config_path.read_bytes())

    def test_extra_params_cannot_override_request_or_contain_nan(self):
        before = self.config.get_all()
        for params in ('{"stream": true}', '{"top_p": NaN}', '[]'):
            self.window.input_additional_params.setPlainText(params)
            self.window._on_save()
            self.assertEqual(before, self.config.get_all())
            self.assertEqual(self.window.result(), 0)

    def test_prompt_edits_survive_switch_and_cancel_discards(self):
        original = deepcopy(self.prompts.prompts)
        self.window.prompt_name_edit.setText("Draft grammar")
        self.window.prompt_combo.setCurrentIndex(1)
        self.window.prompt_name_edit.setText("Draft rewrite")
        self.window.prompt_combo.setCurrentIndex(0)
        self.assertEqual(self.window.prompt_name_edit.text(), "Draft grammar")
        self.window.reject()
        self.assertEqual(self.prompts.prompts, original)
        self.assertFalse(self.prompts.user_prompts_path.exists())

    def test_invalid_prompt_blocks_switch(self):
        self.window.prompt_temp_edit.setText("NaN")
        self.window.prompt_combo.setCurrentIndex(1)
        self.assertEqual(self.window.prompt_combo.currentIndex(), 0)
        self.assertEqual(self.window.prompt_temp_edit.text(), "NaN")

    def test_invalid_chatml_blocks_save_before_any_change(self):
        before = self.config.get_all()
        self.window.prompt_template_edit.setPlainText("<|im_start|>broken")
        self.window.input_model.setText("changed-model")
        self.window._on_save()
        self.assertEqual(self.config.get_all(), before)
        self.assertFalse(self.prompts.user_prompts_path.exists())

    def test_save_commits_all_prompt_drafts_and_removes_key(self):
        self.config.set("api.api_key_encrypted", "old-secret")
        self.window.clear_api_key.setChecked(True)
        self.window.prompt_name_edit.setText("Grammar draft")
        self.window.prompt_combo.setCurrentIndex(1)
        self.window.prompt_name_edit.setText("Rewrite draft")
        self.window._on_save()
        self.assertEqual(self.window.result(), 1)
        self.assertEqual(self.config.get("api.api_key_encrypted"), "")
        self.assertEqual(self.prompts.prompts["grammar_check"]["name"], "Grammar draft")
        self.assertEqual(self.prompts.prompts["rewrite"]["name"], "Rewrite draft")

    def test_failed_config_save_restores_memory_and_prompt_disk(self):
        original_config = self.config.get_all()
        original_prompts = deepcopy(self.prompts.prompts)
        self.window.prompt_name_edit.setText("Unsaved draft")
        with self.assertLogs("ui.settings_window", level="ERROR"):
            with patch.object(self.config, "save", side_effect=OSError("Disk full")):
                self.window._on_save()
        self.assertEqual(self.config.get_all(), original_config)
        self.assertEqual(self.prompts.prompts, original_prompts)
        reloaded = PromptManager(user_prompts_path=str(self.prompts.user_prompts_path))
        self.assertEqual(reloaded.prompts, original_prompts)

    def test_reset_is_discarded_on_cancel_and_removes_override_on_save(self):
        self.prompts.update_prompt("grammar_check", name="Changed")
        self.prompts.save()
        self.window.close()
        self.window = SettingsWindow(self.config, self.config.crypto, self.prompts)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.window._on_reset_prompt()
        self.assertEqual(self.prompts.prompts["grammar_check"]["name"], "Changed")
        self.window.reject()
        self.window = SettingsWindow(self.config, self.config.crypto, self.prompts)
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Yes):
            self.window._on_reset_prompt()
        self.window._on_save()
        self.assertNotIn("grammar_check", self.prompts.user_prompts)
        reloaded = PromptManager(user_prompts_path=str(self.prompts.user_prompts_path))
        self.assertNotIn("grammar_check", reloaded.user_prompts)

    def test_onboarding_rejects_invalid_endpoint(self):
        window = OnboardingWindow()
        self.addCleanup(window.close)
        events = []
        window.setup_completed.connect(lambda *args: events.append(args))
        window.input_base_url.setText("file:///secret")
        window.input_model.setText("model")
        window._on_continue()
        self.assertEqual(events, [])
        self.assertEqual(window.result(), 0)

    def test_popup_requires_instruction_and_hides_before_single_submission(self):
        window = PopupWindow()
        self.addCleanup(window.close)
        window.show_at_position(0, 0, "<b>literal text</b>")
        events = []
        window.action_requested.connect(lambda *args: events.append((window.isVisible(), args)))
        self.assertEqual(window.preview_label.textFormat(), Qt.TextFormat.PlainText)
        window._emit_action("custom")
        self.assertEqual(events, [])
        self.assertTrue(window.isVisible())
        window.prompt_input.setPlainText("Rewrite")
        window._emit_action("custom")
        window._emit_action("custom")
        self.assertEqual(len(events), 1)
        self.assertFalse(events[0][0])
        self.assertEqual(events[0][1], ("custom", "<b>literal text</b>", "Rewrite"))

    def test_recreated_tray_keeps_pause_action_label(self):
        tray = TrayManager()
        with patch.object(tray, "_create_default_icon", wraps=tray._create_default_icon):
            tray.set_paused(True)
            tray.create_tray_icon(str(Path(self.tmp.name) / "missing.ico"))
            self.addCleanup(tray.hide)
            self.assertEqual(tray.action_pause.text(), "Resume")
            self.assertIs(tray.tray_icon.parent(), tray)


if __name__ == "__main__":
    unittest.main()
