import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from core import diagnostics


class DiagnosticsTests(unittest.TestCase):
    def setUp(self):
        self.logger = logging.getLogger('quill.diagnostics')
        self.handlers = self.logger.handlers[:]
        self.level = self.logger.level
        self.logger.handlers = [logging.NullHandler()]
        self.addCleanup(self.restore)

    def restore(self):
        for handler in self.logger.handlers:
            handler.close()
        self.logger.handlers = self.handlers
        self.logger.setLevel(self.level)

    def test_history_rotates_without_recording_exception_text(self):
        with tempfile.TemporaryDirectory() as directory:
            diagnostics.setup_diagnostics(directory)
            handler = self.logger.handlers[-1]
            handler.maxBytes = 180
            for _ in range(25):
                diagnostics.record('extraction.completed', characters=10)
            try:
                raise RuntimeError('secret document and API key')
            except RuntimeError as exc:
                with patch('sys.__excepthook__'):
                    diagnostics.report_unhandled(type(exc), exc, exc.__traceback__)
            handler.close()
            files = list(Path(directory).glob('events.log*'))
            contents = ''.join(file.read_text(encoding='utf-8') for file in files)
            self.assertLessEqual(len(files), 3)
            self.assertIn('python.unhandled', contents)
            self.assertNotIn('secret document', contents)
            self.assertNotIn('API key', contents)

    def test_content_fields_are_rejected(self):
        with self.assertRaises(ValueError):
            diagnostics.record('ai.completed', response='private text')
        with self.assertRaises(ValueError):
            diagnostics.record('private text from a document')

    def test_unwritable_log_does_not_prevent_startup(self):
        with patch.object(Path, 'mkdir', side_effect=PermissionError):
            diagnostics.setup_diagnostics('unwritable')
        self.assertEqual(len(self.logger.handlers), 1)

    def test_caught_constructor_failure_is_recorded_without_exception_text(self):
        import main
        import sys
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(main, 'setup_logging'), \
                 patch.object(main, 'setup_diagnostics', side_effect=lambda: diagnostics.setup_diagnostics(directory)), \
                 patch.object(main, 'SingleInstanceLock', return_value=Mock(acquire=Mock(return_value=True))), \
                 patch.object(main, 'QuillApp', side_effect=RuntimeError('private response')), \
                 patch.object(main, 'QApplication'), \
                 patch.object(main.QMessageBox, 'critical') as dialog, \
                 patch.object(sys, 'excepthook'):
                with self.assertLogs('__main__' if main.__name__ == '__main__' else 'main', level='ERROR'):
                    with self.assertRaises(SystemExit) as raised:
                        main.main()
                self.assertEqual(raised.exception.code, 1)
                dialog.assert_called_once()
                self.assertNotIn('private response', dialog.call_args.args[2])
            for handler in self.logger.handlers:
                handler.close()
            contents = (Path(directory) / 'events.log').read_text(encoding='utf-8')
            self.assertIn('session.failed', contents)
            self.assertNotIn('private response', contents)
