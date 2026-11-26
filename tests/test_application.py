import os
import subprocess
import sys
import textwrap
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from app.application import QuillApp
from core.config_manager import ConfigManager


class ApplicationLifecycleTests(unittest.TestCase):
    @unittest.skipUnless(sys.platform == 'win32', 'Windows paused launch')
    def test_paused_launch_preserves_config_and_registers_only_on_resume(self):
        script = textwrap.dedent('''
            import ctypes
            import tempfile
            from pathlib import Path
            from unittest.mock import Mock, patch
            from PySide6.QtCore import QTimer
            from app.application import QuillApp
            from app.windows_hotkeys import _user32
            from core.config_manager import ConfigManager
            from core.prompt_manager import PromptManager
            api = _user32()
            with tempfile.TemporaryDirectory() as folder:
                config = ConfigManager(str(Path(folder) / 'config.json'))
                config.create_default_config()
                config.set('hotkey.key', '<ctrl>+<alt>+<shift>+<135>')
                config.set('hotkey.quick_key', '')
                config.save()
                original = config.config_path.read_bytes()
                prompts = PromptManager(user_prompts_path=str(Path(folder) / 'prompts.json'))
                provider, tray = Mock(), Mock()
                with patch('app.application.ConfigManager', return_value=config), \
                     patch('app.application.PromptManager', return_value=prompts), \
                     patch('app.application.OAICompatibleProvider', return_value=provider), \
                     patch('app.application.TrayManager', return_value=tray):
                    app = QuillApp(['Quill', '--paused'])
                    assert not app.hotkey_manager.is_active
                    assert not app.hotkey_manager.is_running()
                    tray.set_paused.assert_called_once_with(True)
                    tray.show_message.assert_not_called()
                    assert api.RegisterHotKey(None, 0x4100, 0x4007, 135)
                    api.UnregisterHotKey(None, 0x4100)
                    errors = []
                    def exercise():
                        try:
                            app._on_pause_toggled(False)
                            assert app.hotkey_manager.is_running()
                            duplicate = api.RegisterHotKey(None, 0x4100, 0x4007, 135)
                            if duplicate: api.UnregisterHotKey(None, 0x4100)
                            assert not duplicate
                            assert config.config_path.read_bytes() == original
                            provider.complete.assert_not_called()
                        except Exception as exc:
                            errors.append(repr(exc))
                        finally:
                            app.quit()
                    QTimer.singleShot(0, exercise)
                    QTimer.singleShot(3000, lambda: app.exit(3))
                    assert app.exec() == 0
                    assert not errors, errors
                    assert api.RegisterHotKey(None, 0x4100, 0x4007, 135)
                    api.UnregisterHotKey(None, 0x4100)
        ''')
        result = subprocess.run([sys.executable, '-c', script],
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(sys.platform == 'win32', 'Windows hotkey recovery')
    def test_real_windows_conflict_can_be_fixed_in_settings_and_resumed(self):
        script = textwrap.dedent('''
            import ctypes
            import tempfile
            from pathlib import Path
            from unittest.mock import Mock, patch
            from PySide6.QtCore import QTimer
            from app.application import QuillApp
            from app.windows_hotkeys import _user32
            from core.config_manager import ConfigManager
            from core.prompt_manager import PromptManager

            api = _user32()
            assert api.RegisterHotKey(None, 0x4100, 0x4007, 135)
            try:
                with tempfile.TemporaryDirectory() as folder:
                    config = ConfigManager(str(Path(folder) / 'config.json'))
                    config.create_default_config()
                    config.set('hotkey.key', '<ctrl>+<alt>+<shift>+<135>')
                    config.set('hotkey.quick_key', '')
                    config.save()
                    prompts = PromptManager(user_prompts_path=str(Path(folder) / 'prompts.json'))
                    provider, tray = Mock(), Mock()
                    with patch('app.application.ConfigManager', return_value=config), \
                         patch('app.application.PromptManager', return_value=prompts), \
                         patch('app.application.OAICompatibleProvider', return_value=provider), \
                         patch('app.application.TrayManager', return_value=tray):
                        app = QuillApp([])
                        assert not app.hotkey_manager.is_active
                        tray.set_paused.assert_called_once_with(True)
                        errors = []
                        def exercise():
                            try:
                                app._show_settings()
                                settings = app.settings_window
                                settings.input_hotkey.setText('<ctrl>+<alt>+<shift>+<f11>')
                                settings._on_save()
                                assert settings.result() == 1
                                assert config.get('hotkey.key') == '<ctrl>+<alt>+<shift>+<f11>'
                                assert not app.hotkey_manager.is_active
                                app._on_pause_toggled(False)
                                assert app.hotkey_manager.is_running()
                                duplicate = api.RegisterHotKey(None, 0x4101, 0x4007, 122)
                                if duplicate:
                                    api.UnregisterHotKey(None, 0x4101)
                                assert not duplicate, 'Quill did not register the replacement shortcut.'
                                provider.complete.assert_not_called()
                            except Exception as exc:
                                errors.append(repr(exc))
                            finally:
                                app.quit()
                        QTimer.singleShot(0, exercise)
                        QTimer.singleShot(3000, lambda: app.exit(3))
                        assert app.exec() == 0
                        assert not errors, errors
                        # Cleanup must release the replacement shortcut too.
                        assert api.RegisterHotKey(None, 0x4101, 0x4007, 122)
                        api.UnregisterHotKey(None, 0x4101)
            finally:
                api.UnregisterHotKey(None, 0x4100)
        ''')
        result = subprocess.run([sys.executable, '-c', script],
                                env=dict(os.environ, QT_QPA_PLATFORM='offscreen'),
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_real_qt_event_loop_delivers_worker_result_and_cleans_up(self):
        script = textwrap.dedent('''
            import tempfile
            from pathlib import Path
            from unittest.mock import Mock, patch
            from PySide6.QtCore import QObject, QTimer, Signal
            from app.application import QuillApp
            from core.config_manager import ConfigManager
            from core.prompt_manager import PromptManager

            class TextProcessor(QObject):
                text_extracted = Signal(str)
                text_replaced = Signal()
                operation_failed = Signal(str)
                def replace_text(self, text):
                    assert text == 'replacement'
                    assert app._ai_request_in_progress
                    self.text_replaced.emit()
                    assert not app._ai_request_in_progress
                    observed.append(text)
                    app.quit()
                def cleanup(self):
                    observed.append('cleanup')

            observed = []
            with tempfile.TemporaryDirectory() as folder:
                config = ConfigManager(str(Path(folder) / 'config.json'))
                config.create_default_config()
                prompts = PromptManager(user_prompts_path=str(Path(folder) / 'prompts.json'))
                provider = Mock()
                provider.complete.return_value = 'replacement'
                with patch('app.application.ConfigManager', return_value=config), \
                     patch('app.application.PromptManager', return_value=prompts), \
                     patch('app.application.OAICompatibleProvider', return_value=provider), \
                     patch('app.application.TextProcessor', TextProcessor), \
                     patch('app.application.HotkeyManager'), \
                     patch('app.application.TrayManager'):
                    app = QuillApp([])
                    QTimer.singleShot(0, lambda: app._on_action_requested('rewrite', 'original', ''))
                    QTimer.singleShot(3000, app.quit)
                    assert app.exec() == 0
                    assert observed == ['replacement', 'cleanup'], observed
                    assert app._shutting_down
                    provider.complete.assert_called_once()
        ''')
        env = dict(os.environ, QT_QPA_PLATFORM='offscreen')
        result = subprocess.run([sys.executable, '-c', script], env=env,
                                capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)

    def make_app(self):
        app = SimpleNamespace(
            _shutting_down=False, _start_paused=False, _ai_request_in_progress=True, activeModalWidget=lambda: None,
            _extraction_in_progress=False, _quick_mode=False,
            text_processor=Mock(), ai_provider=Mock(), hotkey_manager=Mock(),
            tray_manager=Mock(), _show_error_dialog=Mock(),
            _request_thread=None, popup_window=None, settings_window=None,
            onboarding_window=None, _ai_completed=Mock(),
            _ui_preload_timer=Mock(),
            _preview_font_timer=Mock(),
            quit=Mock(),
        )
        app._api_setup_error = ''
        app._paste_pending = False
        app._last_response = ''
        app._copy_response = lambda response: QuillApp._copy_response(app, response)
        app._configure_provider = lambda: QuillApp._configure_provider(app)
        app._notify_api_setup_error = lambda: QuillApp._notify_api_setup_error(app)
        app._refresh_popup_prompt_names = lambda: QuillApp._refresh_popup_prompt_names(app)
        return app

    def test_success_remains_busy_until_paste_finishes(self):
        app = self.make_app()
        QuillApp._on_ai_completed(app, 'replacement', '')
        app.text_processor.replace_text.assert_called_once_with('replacement')
        self.assertTrue(app._ai_request_in_progress)
        QuillApp._on_text_replaced(app)
        self.assertFalse(app._ai_request_in_progress)
        with patch('app.application.pyperclip.copy') as copy:
            QuillApp._copy_last_response(app)
        copy.assert_called_once_with('replacement')

    def test_only_replacement_failure_offers_the_pending_response(self):
        app = self.make_app()
        QuillApp._on_ai_completed(app, 'generated result', '')
        QuillApp._on_text_operation_failed(app, 'source changed')
        app._show_error_dialog.assert_called_once_with(
            'Text Operation Failed', 'source changed', response='generated result',
        )
        app._show_error_dialog.reset_mock()
        QuillApp._on_text_operation_failed(app, 'unrelated copy failure')
        app._show_error_dialog.assert_called_once_with(
            'Text Operation Failed', 'unrelated copy failure', response='',
        )

    def test_error_and_empty_response_leave_original_untouched(self):
        for response, error in [('', 'timeout'), (' \n', '')]:
            with self.subTest(response=response, error=error):
                app = self.make_app()
                QuillApp._on_ai_completed(app, response, error)
                app.text_processor.replace_text.assert_not_called()
                app._show_error_dialog.assert_called_once()
                self.assertFalse(app._ai_request_in_progress)

    def test_late_result_after_quit_is_ignored(self):
        app = self.make_app()
        app._shutting_down = True
        QuillApp._on_ai_completed(app, 'replacement', '')
        app.text_processor.replace_text.assert_not_called()

    def test_quick_hotkey_does_not_change_an_active_extraction(self):
        app = self.make_app()
        app._ai_request_in_progress = False
        app._extraction_in_progress = True
        QuillApp._on_quick_hotkey_pressed(app, 0, 0)
        app.text_processor.extract_selected_text.assert_not_called()
        self.assertFalse(app._quick_mode)

    def test_settings_are_blocked_during_request(self):
        app = self.make_app()
        QuillApp._show_settings(app)
        app.tray_manager.show_message.assert_called_once()

    def test_preload_waits_for_text_work_and_stops_on_shutdown(self):
        app = self.make_app()
        app._create_settings_window = Mock()
        QuillApp._preload_windows(app)
        app._create_settings_window.assert_not_called()
        app._ui_preload_timer.start.assert_called_once_with(250)
        app._ui_preload_timer.start.reset_mock()
        app._shutting_down = True
        QuillApp._preload_windows(app)
        app._create_settings_window.assert_not_called()
        app._ui_preload_timer.start.assert_not_called()

    def test_preview_fonts_wait_until_no_work_or_visible_settings(self):
        app = self.make_app()
        app.popup_window = Mock(isVisible=Mock(return_value=False))
        app.settings_window = Mock(isVisible=Mock(return_value=True))
        app.activePopupWidget = Mock()
        for ai_busy, settings_visible, menu_visible in ((True, False, False), (False, True, False), (False, False, True)):
            app._ai_request_in_progress = ai_busy
            app.settings_window.isVisible.return_value = settings_visible
            app.activePopupWidget.return_value = object() if menu_visible else None
            QuillApp._preload_preview_fonts(app)
        app.popup_window.prepare_preview_fonts.assert_not_called()
        self.assertEqual(app._preview_font_timer.start.call_count, 3)
        app.settings_window.isVisible.return_value = False
        app.activePopupWidget.return_value = None
        QuillApp._preload_preview_fonts(app)
        app.popup_window.prepare_preview_fonts.assert_called_once()
        app._shutting_down = True
        QuillApp._preload_preview_fonts(app)
        app.popup_window.prepare_preview_fonts.assert_called_once()

    def test_cleanup_defers_client_close_to_active_worker(self):
        app = self.make_app()
        app._request_thread = Mock()
        app._request_thread.is_alive.return_value = True
        QuillApp._cleanup(app)
        app.ai_provider.close.assert_not_called()
        app.text_processor.cleanup.assert_called_once()
        QuillApp._cleanup(app)
        app.text_processor.cleanup.assert_called_once()
        app.ai_provider.complete.return_value = 'late response'
        QuillApp._process_ai_request(app, [], 0.5, {})
        app.ai_provider.close.assert_called_once()
        app._ai_completed.emit.assert_not_called()

    def test_cleanup_closes_idle_client(self):
        app = self.make_app()
        QuillApp._cleanup(app)
        app.ai_provider.close.assert_called_once()

    def test_input_failure_unblocks_application(self):
        app = self.make_app()
        app._extraction_in_progress = True
        app._quick_mode = True
        QuillApp._on_text_operation_failed(app, 'Target changed')
        self.assertFalse(app._ai_request_in_progress)
        self.assertFalse(app._extraction_in_progress)
        self.assertFalse(app._quick_mode)

    def test_worker_start_failure_releases_extraction_guard(self):
        app = self.make_app()
        app._ai_request_in_progress = False
        app._quick_mode = True
        app.text_processor.extract_selected_text.side_effect = RuntimeError('worker unavailable')
        app._on_text_operation_failed = lambda message: QuillApp._on_text_operation_failed(app, message)
        QuillApp._begin_extraction(app)
        self.assertFalse(app._extraction_in_progress)
        self.assertFalse(app._quick_mode)
        self.assertFalse(app._ai_request_in_progress)
        app._show_error_dialog.assert_called_once()

    def test_failed_resume_keeps_tray_paused_and_reports_registration_error(self):
        app = self.make_app()
        app.hotkey_manager.resume.side_effect = RuntimeError('Shortcut busy')
        QuillApp._on_pause_toggled(app, False)
        app.tray_manager.set_paused.assert_called_once_with(True)
        app._show_error_dialog.assert_called_once_with('Shortcut Registration Failed', 'Shortcut busy')

    def test_startup_conflict_keeps_tray_and_settings_recovery_available(self):
        app = self.make_app()
        app.config_manager = Mock()
        settings = {'api.base_url': 'http://localhost/v1', 'api.model': 'model',
                    'hotkey.key': '<ctrl>+<space>', 'hotkey.quick_key': ''}
        app.config_manager.get.side_effect = lambda key, default=None: settings.get(key, default)
        app.config_manager.get_api_key.return_value = ''
        app._create_popup_window = Mock()
        app.hotkey_manager.start.side_effect = RuntimeError('Shortcut busy')
        with self.assertLogs('app.application', level='WARNING'), patch('app.application.QTimer.singleShot') as quit_timer:
            QuillApp._start_app(app)
        app.tray_manager.create_tray_icon.assert_called_once()
        app._create_popup_window.assert_called_once()
        app.hotkey_manager.pause.assert_called_once()
        app.tray_manager.set_paused.assert_called_once_with(True)
        app.tray_manager.show_message.assert_called_once()
        quit_timer.assert_not_called()

    def test_unreadable_api_key_keeps_startup_and_settings_recovery_available(self):
        app = self.make_app()
        app._ai_request_in_progress = False
        app.config_manager = Mock()
        settings = {'api.base_url': 'http://localhost/v1', 'api.model': 'model'}
        app.config_manager.get.side_effect = lambda key, default=None: settings.get(key, default)
        app.config_manager.get_api_key.side_effect = [RuntimeError('cannot decrypt'), 'new key']
        app._create_popup_window = Mock()
        QuillApp._start_app(app)

        app.tray_manager.create_tray_icon.assert_called_once()
        app.tray_manager.show_message.assert_called_once()
        app._ui_preload_timer.start.assert_called_once_with(250)
        app.hotkey_manager.start.assert_called_once()
        app.ai_provider.configure.assert_not_called()
        app.config_manager.save.assert_not_called()
        QuillApp._on_action_requested(app, 'rewrite', 'selected text', '')
        self.assertFalse(app._ai_request_in_progress)
        app._show_error_dialog.assert_called_once_with('Quill API setup', app._api_setup_error)

        QuillApp._on_settings_saved(app, {})
        app.ai_provider.configure.assert_called_once_with('http://localhost/v1', 'new key', 'model')
        self.assertFalse(app._api_setup_error)

    def test_failed_onboarding_encryption_does_not_finish_setup(self):
        with tempfile.TemporaryDirectory() as folder:
            app = self.make_app()
            app.config_manager = ConfigManager(str(Path(folder) / 'config.json'))
            app._start_app = Mock()
            with patch.object(app.config_manager.crypto, 'encrypt', side_effect=RuntimeError('encrypt failed')), \
                 patch('app.application.QMessageBox.critical'), self.assertLogs('app.application', level='ERROR'):
                QuillApp._on_onboarding_completed(app, 'http://localhost/v1', 'new key', 'model')
            self.assertFalse(app.config_manager.config_path.exists())
            app._start_app.assert_not_called()

            with patch.object(app.config_manager.crypto, 'encrypt', return_value='encrypted-key'):
                QuillApp._on_onboarding_completed(app, 'http://localhost/v1', 'new key', 'model')
            app._start_app.assert_called_once_with()
            self.assertEqual(app.config_manager.get('api.base_url'), 'http://localhost/v1')
            self.assertEqual(app.config_manager.get('api.api_key_encrypted'), 'encrypted-key')

    def test_unexpected_provider_error_does_not_display_exception_text(self):
        app = self.make_app()
        app.ai_provider.complete.side_effect = RuntimeError('private selection')
        with patch('app.application.record_exception') as recorded:
            QuillApp._process_ai_request(app, [], 0.5, {})
        self.assertEqual(recorded.call_args.args[0], 'ai.unexpected_failure')
        self.assertNotIn('private selection', app._ai_completed.emit.call_args.args[1])

    def test_caught_startup_error_records_only_redacted_traceback(self):
        app = self.make_app()
        app.config_manager = Mock()
        app.config_manager.load.side_effect = RuntimeError('private settings')
        with patch('app.application.record_exception') as recorded, \
             patch('app.application.QMessageBox.critical'), \
             patch('app.application.QTimer.singleShot'), \
             self.assertLogs('app.application', level='ERROR'):
            QuillApp._start_app(app)
        self.assertEqual(recorded.call_args.args[0], 'startup.failed')
        self.assertEqual(len(recorded.call_args.args), 2)


if __name__ == '__main__':
    unittest.main()
