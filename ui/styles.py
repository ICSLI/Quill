"""
Quill UI 스타일

VS Code Dark+ 테마를 참고한 미니멀리스틱 다크 테마입니다.
"""

# VS Code Dark+ 스타일 다크 테마
DARK_THEME = """
QWidget {
    background-color: #1e1e1e;
    color: #d4d4d4;
    font-family: 'Segoe UI', 'Arial', sans-serif;
    font-size: 13px;
}

QMainWindow {
    background-color: #1e1e1e;
}

/* 버튼 스타일 */
QPushButton {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    padding: 8px 16px;
    color: #d4d4d4;
    font-weight: 500;
}

QPushButton:hover {
    background-color: #3e3e42;
    border-color: #007acc;
}

QPushButton:pressed {
    background-color: #007acc;
    border-color: #007acc;
}

QPushButton:disabled {
    background-color: #2d2d30;
    border-color: #3e3e42;
    color: #6e6e6e;
}

/* 빠른 작업 버튼 (작은 버튼) */
QPushButton#quickActionButton {
    padding: 6px 12px;
    font-size: 12px;
}

/* 전송 버튼 (강조) */
QPushButton#sendButton {
    background-color: #007acc;
    border-color: #007acc;
    color: #ffffff;
    font-weight: bold;
}

QPushButton#sendButton:hover {
    background-color: #005a9e;
    border-color: #005a9e;
}

/* 텍스트 입력 필드 */
QLineEdit, QTextEdit, QPlainTextEdit {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    padding: 6px;
    color: #d4d4d4;
    selection-background-color: #007acc;
    selection-color: #ffffff;
}

QLineEdit:focus, QTextEdit:focus, QPlainTextEdit:focus {
    border-color: #007acc;
}

/* 텍스트 입력 필드 읽기 전용 */
QLineEdit:read-only {
    background-color: #2d2d30;
    color: #858585;
}

/* 텍스트 에디터 코너 (스크롤바 교차점) */
QTextEdit::corner {
    background-color: transparent;
    border: none;
}

/* 리스트 위젯 */
QListWidget {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    padding: 4px;
    color: #d4d4d4;
    outline: none;
}

QListWidget::item {
    padding: 6px;
    border-radius: 3px;
}

QListWidget::item:selected {
    background-color: #007acc;
    color: #ffffff;
}

QListWidget::item:hover {
    background-color: #3e3e42;
}

/* 콤보박스 */
QComboBox {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    border-radius: 4px;
    padding: 6px;
    color: #d4d4d4;
}

QComboBox:hover {
    border-color: #007acc;
}

QComboBox:focus {
    border-color: #007acc;
}

QComboBox::drop-down {
    width: 0;
    border: none;
}

QComboBox QAbstractItemView {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    selection-background-color: #007acc;
    selection-color: #ffffff;
    outline: none;
}

/* 레이블 */
QLabel {
    color: #d4d4d4;
    background-color: transparent;
}

QLabel#titleLabel {
    font-size: 16px;
    font-weight: bold;
    color: #ffffff;
}

QLabel#subtitleLabel {
    font-size: 11px;
    color: #858585;
}

QLabel#iconContainer {
    background-color: #2d2d30;
    border-radius: 8px;
}

QLabel#previewLabel {
    color: #d4d4d4;
    font-size: 13px;
    font-weight: 500;
}

/* 그룹 박스 */
QGroupBox {
    border: 1px solid #3e3e42;
    border-radius: 4px;
    margin-top: 12px;
    padding-top: 12px;
    font-weight: bold;
    color: #d4d4d4;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 8px;
    color: #d4d4d4;
}

/* 체크박스 */
QCheckBox {
    spacing: 8px;
    color: #d4d4d4;
}

QCheckBox::indicator {
    width: 16px;
    height: 16px;
    border: 1px solid #3e3e42;
    border-radius: 3px;
    background-color: #2d2d30;
}

QCheckBox::indicator:checked {
    background-color: #007acc;
    border-color: #007acc;
}

QCheckBox::indicator:hover {
    border-color: #007acc;
}

/* 스크롤바 */
QScrollBar:vertical {
    background-color: transparent;
    width: 14px;
    margin: 0;
    border: none;
}

QScrollBar::handle:vertical {
    background-color: #424242;
    min-height: 20px;
    margin: 2px 2px 2px 2px;
}

QScrollBar::handle:vertical:hover {
    background-color: #4e4e4e;
}

QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
    height: 0px;
    background: transparent;
}

QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
    background: transparent;
}

QScrollBar:horizontal {
    background-color: transparent;
    height: 14px;
    margin: 0;
    border: none;
}

QScrollBar::handle:horizontal {
    background-color: #424242;
    min-width: 20px;
    margin: 2px 2px 2px 2px;
}

QScrollBar::handle:horizontal:hover {
    background-color: #4e4e4e;
}

QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
    width: 0px;
    background: transparent;
}

QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
    background: transparent;
}

/* 탭 위젯 */
QTabWidget::pane {
    border: 1px solid #3e3e42;
    background-color: #1e1e1e;
}

QTabBar::tab {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    border-bottom: none;
    padding: 8px 16px;
    color: #d4d4d4;
}

QTabBar::tab:selected {
    background-color: #1e1e1e;
    color: #ffffff;
    border-bottom: 2px solid #007acc;
}

QTabBar::tab:hover {
    background-color: #3e3e42;
}

/* 메뉴 */
QMenu {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    color: #d4d4d4;
}

QMenu::item {
    padding: 8px 24px;
}

QMenu::item:selected {
    background-color: #007acc;
    color: #ffffff;
}

QMenu::separator {
    height: 1px;
    background-color: #3e3e42;
    margin: 4px 0;
}

/* 툴팁 */
QToolTip {
    background-color: #2d2d30;
    border: 1px solid #3e3e42;
    color: #d4d4d4;
    padding: 4px;
}

/* 다이얼로그 */
QDialog {
    background-color: #1e1e1e;
}

/* 메시지 박스 */
QMessageBox {
    background-color: #1e1e1e;
}

QMessageBox QPushButton {
    min-width: 80px;
}
"""


def apply_dark_theme(widget):
    """
    위젯에 다크 테마 적용

    Args:
        widget: Qt 위젯 (QWidget, QApplication 등)
    """
    widget.setStyleSheet(DARK_THEME)
