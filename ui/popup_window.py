"""
메인 팝업 윈도우

마우스 위치에 표시되는 메인 UI입니다.
빠른 작업 버튼과 프롬프트 입력칸을 포함합니다.
"""

import logging
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QTextEdit, QLabel, QFrame
)
from PySide6.QtCore import Qt, Signal, QEvent
from PySide6.QtGui import QKeyEvent, QCursor, QScreen, QIcon

from ui.styles import apply_dark_theme


logger = logging.getLogger(__name__)


class PopupWindow(QWidget):
    """메인 팝업 윈도우"""

    # Signal: 작업 요청 (prompt_key, text, instruction)
    action_requested = Signal(str, str, str)

    def __init__(self, parent=None):
        """PopupWindow 초기화"""
        super().__init__(parent)

        self.selected_text = ""

        # 윈도우 플래그 설정
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Popup  # 외부 클릭 시 자동 닫기
        )

        self._setup_ui()
        apply_dark_theme(self)

        logger.debug("PopupWindow initialized")

    def _setup_ui(self):
        """UI 구성"""
        # 팝업 너비 고정
        self.setFixedWidth(280)

        layout = QVBoxLayout()
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # 헤더 섹션 (아이콘 + 텍스트 미리보기)
        header_layout = QHBoxLayout()
        header_layout.setSpacing(10)

        # 아이콘 컨테이너 (36x36 아이콘)
        self.icon_container = QLabel()
        self.icon_container.setObjectName("iconContainer")
        self.icon_container.setFixedSize(40, 40)
        self.icon_container.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._load_icon()
        header_layout.addWidget(self.icon_container)

        # 텍스트 정보 섹션
        text_info_layout = QVBoxLayout()
        text_info_layout.setSpacing(2)

        # 미리보기 라벨
        self.preview_label = QLabel("Select text to process")
        self.preview_label.setObjectName("previewLabel")
        text_info_layout.addWidget(self.preview_label)

        self.char_count_label = QLabel("0 characters")
        self.char_count_label.setObjectName("subtitleLabel")
        text_info_layout.addWidget(self.char_count_label)

        header_layout.addLayout(text_info_layout, 1)  # stretch=1
        layout.addLayout(header_layout)

        # 구분선
        separator = QFrame()
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator)

        # 빠른 작업 버튼 (2행)
        quick_actions_1 = QHBoxLayout()
        quick_actions_1.setSpacing(8)

        self.btn_grammar = QPushButton("Grammar Check")
        self.btn_grammar.setObjectName("quickActionButton")
        self.btn_grammar.clicked.connect(lambda: self._emit_action("grammar_check"))
        quick_actions_1.addWidget(self.btn_grammar)

        self.btn_rewrite = QPushButton("Rewrite")
        self.btn_rewrite.setObjectName("quickActionButton")
        self.btn_rewrite.clicked.connect(lambda: self._emit_action("rewrite"))
        quick_actions_1.addWidget(self.btn_rewrite)

        layout.addLayout(quick_actions_1)

        quick_actions_2 = QHBoxLayout()
        quick_actions_2.setSpacing(8)

        self.btn_summarize = QPushButton("Summarize")
        self.btn_summarize.setObjectName("quickActionButton")
        self.btn_summarize.clicked.connect(lambda: self._emit_action("summarize"))
        quick_actions_2.addWidget(self.btn_summarize)

        self.btn_translate = QPushButton("Translate")
        self.btn_translate.setObjectName("quickActionButton")
        self.btn_translate.clicked.connect(lambda: self._emit_action("translate"))
        quick_actions_2.addWidget(self.btn_translate)

        layout.addLayout(quick_actions_2)

        # 구분선
        separator2 = QFrame()
        separator2.setFrameShape(QFrame.Shape.HLine)
        separator2.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(separator2)

        # 프롬프트 입력칸
        prompt_label = QLabel("Custom Instruction:")
        prompt_label.setObjectName("subtitleLabel")
        layout.addWidget(prompt_label)

        self.prompt_input = QTextEdit()
        self.prompt_input.setPlaceholderText(
            "Enter custom instruction here...\n"
            "(Press Enter to send, Shift+Enter for newline)"
        )
        self.prompt_input.setFixedHeight(80)
        self.prompt_input.installEventFilter(self)
        layout.addWidget(self.prompt_input)

        # 전송 버튼
        self.btn_send = QPushButton("Send")
        self.btn_send.setObjectName("sendButton")
        self.btn_send.setFixedHeight(36)
        self.btn_send.clicked.connect(lambda: self._emit_action("custom"))
        layout.addWidget(self.btn_send)

        # ESC로 닫기 안내
        help_label = QLabel("Press ESC to close")
        help_label.setObjectName("subtitleLabel")
        help_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(help_label)

        self.setLayout(layout)

    def eventFilter(self, obj, event):
        """
        이벤트 필터 - prompt_input에서 Enter/Shift+Enter 처리
        """
        # prompt_input의 키 이벤트 처리
        if obj == self.prompt_input and event.type() == QEvent.Type.KeyPress:
            if event.key() == Qt.Key.Key_Return or event.key() == Qt.Key.Key_Enter:
                modifiers = event.modifiers()
                if modifiers & Qt.KeyboardModifier.ShiftModifier:
                    # Shift+Enter: 줄바꿈 (기본 동작)
                    return False
                else:
                    # Enter: 전송
                    self._emit_action("custom")
                    return True

        return super().eventFilter(obj, event)

    def keyPressEvent(self, event: QKeyEvent):
        """키 입력 이벤트: ESC로 닫기"""
        if event.key() == Qt.Key.Key_Escape:
            self.close()
        else:
            super().keyPressEvent(event)

    def _load_icon(self):
        """아이콘 로드 및 설정"""
        from PySide6.QtCore import QSize

        project_root = Path(__file__).parent.parent

        # 아이콘 파일 경로 (우선순위: icon_alpha.ico > icon.ico)
        icon_paths = [
            project_root / "resources" / "icon_alpha.ico",
            project_root / "resources" / "icon.ico",
            project_root / "_internal" / "resources" / "icon_alpha.ico",
            project_root / "_internal" / "resources" / "icon.ico",
        ]

        target_size = 36  # 40x40 컨테이너에 맞게 크기 조정

        for icon_path in icon_paths:
            if icon_path.exists():
                # QIcon을 사용하면 ICO 파일에서 적절한 크기를 선택함
                icon = QIcon(str(icon_path))
                if not icon.isNull():
                    # 64x64에서 36x36로 스케일 다운 (더 선명함)
                    pixmap = icon.pixmap(QSize(64, 64))
                    if not pixmap.isNull():
                        scaled_pixmap = pixmap.scaled(
                            target_size, target_size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation
                        )
                        self.icon_container.setPixmap(scaled_pixmap)
                        logger.debug(f"Loaded icon from: {icon_path}")
                        return

        logger.warning("Could not load icon for popup header")

    def _update_preview(self, text: str):
        """텍스트 미리보기 업데이트"""
        if not text:
            self.preview_label.setText("Select text to process")
            self.char_count_label.setText("0 characters")
            return

        # 글자수 표시 (전체 텍스트 길이)
        char_count = len(text)
        if char_count == 1:
            self.char_count_label.setText("1 character")
        else:
            self.char_count_label.setText(f"{char_count} characters")

        # 성능 최적화: 먼저 앞부분만 추출 (최대 50자면 충분)
        preview_source = text[:50]

        # 줄바꿈을 공백으로 변환
        clean_text = preview_source.replace('\n', ' ').replace('\r', '')

        # QFontMetrics로 수동 truncate (elidedText가 CJK에서 부정확함)
        from PySide6.QtGui import QFontMetrics
        fm = QFontMetrics(self.preview_label.font())

        # 사용 가능한 너비 (팝업 280 - 마진 24 - 아이콘 40 - 간격 10 = 206, 여유분 16px)
        max_width = 190

        # 글자 단위로 truncate
        ellipsis = "..."
        ellipsis_width = fm.horizontalAdvance(ellipsis)
        quote_width = fm.horizontalAdvance('""')

        truncated = clean_text
        while fm.horizontalAdvance(truncated) + quote_width > max_width and len(truncated) > 0:
            truncated = truncated[:-1]

        # 원본 텍스트가 truncated보다 길면 말줄임표 추가
        if len(text) > len(truncated):
            # 말줄임표 공간 확보
            while fm.horizontalAdvance(truncated) + quote_width + ellipsis_width > max_width and len(truncated) > 0:
                truncated = truncated[:-1]
            preview_text = f'"{truncated}..."'
        else:
            preview_text = f'"{truncated}"'

        self.preview_label.setText(preview_text)

    def show_at_position(self, x: int, y: int, text: str):
        """
        특정 위치에 팝업 표시

        Args:
            x: X 좌표
            y: Y 좌표
            text: 선택된 텍스트
        """
        self.selected_text = text

        # 텍스트 미리보기 업데이트
        self._update_preview(text)

        # 위젯 크기 조정
        self.adjustSize()

        # 화면 경계 확인
        screen = self._get_screen_at(x, y)
        if screen:
            screen_geometry = screen.geometry()

            # 팝업 크기
            popup_width = self.width()
            popup_height = self.height()

            # 위치 조정
            new_x = x
            new_y = y + 20  # 커서 아래 20픽셀

            # 우측 경계 체크
            if new_x + popup_width > screen_geometry.right():
                new_x = screen_geometry.right() - popup_width

            # 하단 경계 체크
            if new_y + popup_height > screen_geometry.bottom():
                new_y = y - popup_height - 10  # 커서 위로

            # 좌측 경계 체크
            if new_x < screen_geometry.left():
                new_x = screen_geometry.left()

            # 상단 경계 체크
            if new_y < screen_geometry.top():
                new_y = screen_geometry.top()

            self.move(new_x, new_y)

        else:
            # 화면을 찾을 수 없으면 그냥 해당 위치에 표시
            self.move(x, y + 20)

        # 표시
        self.show()
        self.raise_()  # 최상위로
        self.activateWindow()

        # 약간의 지연 후 포커스 (이벤트 필터가 올바르게 작동하도록)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(50, lambda: self.prompt_input.setFocus())

        logger.debug(f"Popup shown at ({x}, {y}), text length: {len(text)}")

    def _get_screen_at(self, x: int, y: int) -> QScreen:
        """
        특정 좌표의 스크린 가져오기

        Args:
            x: X 좌표
            y: Y 좌표

        Returns:
            QScreen 객체 또는 None
        """
        from PySide6.QtGui import QGuiApplication

        for screen in QGuiApplication.screens():
            if screen.geometry().contains(x, y):
                return screen

        # 못 찾으면 기본 스크린 반환
        return QGuiApplication.primaryScreen()

    def _emit_action(self, prompt_key: str):
        """
        작업 시그널 발생

        Args:
            prompt_key: 프롬프트 키 (grammar_check, rewrite, etc.)
        """
        instruction = self.prompt_input.toPlainText().strip()

        logger.info(f"Action requested: {prompt_key}, instruction length: {len(instruction)}")

        # Signal 발생
        self.action_requested.emit(prompt_key, self.selected_text, instruction)

        # 입력칸 초기화 및 숨기기
        self.prompt_input.clear()
        self.hide()


# 테스트 코드
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    window = PopupWindow()

    # Signal 연결 (테스트)
    def on_action_requested(prompt_key, text, instruction):
        print(f"\nAction requested:")
        print(f"  Prompt key: {prompt_key}")
        print(f"  Text: {text[:50]}..." if text else "  Text: (empty)")
        print(f"  Instruction: {instruction[:50]}..." if instruction else "  Instruction: (empty)")

    window.action_requested.connect(on_action_requested)

    # 마우스 위치에 팝업 표시
    cursor_pos = QCursor.pos()
    test_text = "This is a test text that user selected."
    window.show_at_position(cursor_pos.x(), cursor_pos.y(), test_text)

    sys.exit(app.exec())
