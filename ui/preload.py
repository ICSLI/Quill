"""Prepare a hidden window without showing it or entering a nested event loop."""

from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt


def prepare_hidden_window(window):
    if window.isVisible():
        return
    window.ensurePolished()
    window.adjustSize()
    window.winId()
    ratio = window.devicePixelRatioF()
    image = QPixmap(window.size() * ratio)
    image.setDevicePixelRatio(ratio)
    image.fill(Qt.GlobalColor.transparent)
    window.render(image)
