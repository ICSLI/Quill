"""Bounded local event history without document content or credentials."""

import json
import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
import traceback


_logger = logging.getLogger('quill.diagnostics')
_logger.propagate = False
_logger.addHandler(logging.NullHandler())


def record(event, **counts):
    """Only fixed event names and numeric state belong in this log."""
    if not isinstance(event, str) or any(c not in 'abcdefghijklmnopqrstuvwxyz_.' for c in event):
        raise ValueError('Diagnostic events must be fixed identifiers.')
    if any(type(value) not in (int, bool) for value in counts.values()):
        raise ValueError('Diagnostic fields must contain only counts or flags.')
    _logger.info(json.dumps({'event': event, **counts}, separators=(',', ':')))


def setup_diagnostics(directory=None):
    """A logging failure must never prevent the app from starting."""
    if any(isinstance(handler, RotatingFileHandler) for handler in _logger.handlers):
        return
    try:
        folder = Path(directory) if directory is not None else Path(
            os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')
        ) / 'Quill' / 'logs'
        folder.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(folder / 'events.log', maxBytes=262144,
                                      backupCount=2, encoding='utf-8')
        handler.setFormatter(logging.Formatter('%(asctime)s %(message)s'))
        _logger.addHandler(handler)
        _logger.setLevel(logging.INFO)
        record('session.started', pid=os.getpid())
    except OSError:
        pass


def record_exception(event, tb):
    # Exception messages may contain API responses. Keep only code locations.
    frames = traceback.extract_tb(tb)[-20:]
    _logger.error(json.dumps({'event': event,
                              'frames': [{'file': Path(frame.filename).name,
                                          'function': frame.name, 'line': frame.lineno}
                                         for frame in frames]}))


def report_unhandled(exc_type, exc_value, tb):
    record_exception('python.unhandled', tb)
    sys.__excepthook__(exc_type, exc_value, tb)
