"""Real Qt coverage for invisible preloading and fresh settings drafts."""

import os
import subprocess
import sys
import textwrap
import unittest


class PreloadTests(unittest.TestCase):
    def run_script(self, script, platform='offscreen'):
        result = subprocess.run([sys.executable, '-c', textwrap.dedent(script)],
                                env=dict(os.environ, QT_QPA_PLATFORM=platform),
                                capture_output=True, text=True, timeout=15)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_render_failure_keeps_normal_popup_and_settings_available(self):
        self.run_script('''
            import tempfile
            from pathlib import Path
            from unittest.mock import Mock, patch
            from app.application import QuillApp
            from core.config_manager import ConfigManager
            from core.prompt_manager import PromptManager
            with tempfile.TemporaryDirectory() as folder:
                config = ConfigManager(str(Path(folder) / 'config.json'))
                config.create_default_config()
                config.save()
                prompts = PromptManager(user_prompts_path=str(Path(folder) / 'prompts.json'))
                with patch('app.application.ConfigManager', return_value=config), \
                     patch('app.application.PromptManager', return_value=prompts), \
                     patch('app.application.OAICompatibleProvider'), \
                     patch('app.application.HotkeyManager'), \
                     patch('app.application.TrayManager'), \
                     patch('app.application.prepare_hidden_window', side_effect=RuntimeError('render unavailable')):
                    app = QuillApp([])
                    assert app.popup_window is not None
                    app._ui_preload_timer.stop()
                    app._preload_windows()
                    settings = app.settings_window
                    assert settings is not None and not settings.isVisible()
                    app._show_settings()
                    assert app.settings_window is settings and settings.isVisible()
                    settings.reject()
                    app.popup_window.show_at_position(0, 0, 'diagnostic sample')
                    assert app.popup_window.isVisible()
                    app._cleanup()
        ''')

    def test_preloaded_settings_are_used_and_cancelled_drafts_are_discarded(self):
        self.run_script('''
            import tempfile
            from pathlib import Path
            from unittest.mock import Mock, patch
            from PySide6.QtCore import QTimer
            from app.application import QuillApp
            from core.config_manager import ConfigManager
            from core.prompt_manager import PromptManager
            errors = []
            with tempfile.TemporaryDirectory() as folder:
                config = ConfigManager(str(Path(folder) / 'config.json'))
                config.create_default_config()
                config.save()
                original = config.config_path.read_bytes()
                prompts = PromptManager(user_prompts_path=str(Path(folder) / 'prompts.json'))
                provider = Mock()
                with patch('app.application.ConfigManager', return_value=config), \
                     patch('app.application.PromptManager', return_value=prompts), \
                     patch('app.application.OAICompatibleProvider', return_value=provider), \
                     patch('app.application.HotkeyManager'), \
                     patch('app.application.TrayManager'):
                    app = QuillApp([])
                    def check(action):
                        try:
                            action()
                        except Exception as exc:
                            errors.append(repr(exc))
                            app.quit()
                    def first_open():
                        global first
                        first = app.settings_window
                        assert first is not None and not first.isVisible()
                        assert not app.popup_window.isVisible()
                        assert app.activeModalWidget() is None
                        assert app.activePopupWidget() is None
                        assert config.config_path.read_bytes() == original
                        app._show_settings()
                        assert app.settings_window is first and first.isVisible()
                        first.input_model.setText('unsaved model')
                        first.input_api_key.setText('unsaved key')
                        first.prompt_name_edit.setText('unsaved prompt')
                        app._show_settings()
                        assert app.settings_window is first
                        assert first.input_model.text() == 'unsaved model'
                        first.reject()
                        assert app.settings_window is None
                        QTimer.singleShot(400, lambda: check(after_cancel))
                    def after_cancel():
                        second = app.settings_window
                        assert second is not None and second is not first
                        assert not second.isVisible()
                        assert second.input_model.text() == config.get('api.model')
                        assert not second.input_api_key.text()
                        assert second.prompt_name_edit.text() != 'unsaved prompt'
                        assert config.config_path.read_bytes() == original
                        assert not prompts.user_prompts_path.exists()
                        app._show_settings()
                        second.input_model.setText('saved model')
                        second._on_save()
                        assert config.get('api.model') == 'saved model'
                        assert app.settings_window is None
                        QTimer.singleShot(400, lambda: check(after_save))
                    def after_save():
                        assert app.settings_window is not None
                        assert app.settings_window.input_model.text() == 'saved model'
                        assert not app.settings_window.isVisible()
                        provider.complete.assert_not_called()
                        app.quit()
                    QTimer.singleShot(400, lambda: check(first_open))
                    QTimer.singleShot(5000, lambda: app.exit(3))
                    assert app.exec() == 0
                    assert not errors, errors
                    assert not app._ui_preload_timer.isActive()
        ''')

    @unittest.skipUnless(sys.platform == 'win32', 'Windows hidden native windows')
    def test_native_preload_never_shows_or_activates_windows(self):
        self.run_script('''
            import ctypes
            import tempfile
            from pathlib import Path
            from PySide6.QtCore import QEvent, QObject
            from PySide6.QtWidgets import QApplication
            from core.config_manager import ConfigManager
            from core.prompt_manager import PromptManager
            from ui.popup_window import PopupWindow
            from ui.settings_window import SettingsWindow
            from ui.preload import prepare_hidden_window
            api = ctypes.WinDLL('user32')
            api.GetForegroundWindow.restype = ctypes.c_void_p
            api.IsWindowVisible.argtypes = [ctypes.c_void_p]
            app = QApplication([])
            before = api.GetForegroundWindow()
            with tempfile.TemporaryDirectory() as folder:
                config = ConfigManager(str(Path(folder) / 'config.json'))
                config.create_default_config()
                prompts = PromptManager(user_prompts_path=str(Path(folder) / 'prompts.json'))
                class Events(QObject):
                    def __init__(self):
                        super().__init__()
                        self.paint = 0
                        self.shown = 0
                    def eventFilter(self, obj, event):
                        if event.type() == QEvent.Type.Paint: self.paint += 1
                        if event.type() == QEvent.Type.Show: self.shown += 1
                        return False
                for window in (PopupWindow(), SettingsWindow(config, config.crypto, prompts)):
                    events = Events()
                    window.installEventFilter(events)
                    prepare_hidden_window(window)
                    app.processEvents()
                    assert window.windowHandle() is not None
                    assert not window.isVisible()
                    assert not api.IsWindowVisible(int(window.winId()))
                    assert events.paint > 0 and events.shown == 0
                    assert app.activePopupWidget() is None
                    assert app.activeModalWidget() is None
                    assert api.GetForegroundWindow() == before
                    window.close()
        ''', platform='windows')
