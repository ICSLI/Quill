"""
온보딩 창

첫 실행 시 API 설정을 받는 창입니다.
"""

import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QMessageBox
)
from PySide6.QtCore import Qt, Signal

from ui.styles import apply_dark_theme


logger = logging.getLogger(__name__)


class OnboardingWindow(QDialog):
    """온보딩 창"""

    # Signal: 설정 완료 시 발생 (base_url, api_key, model)
    setup_completed = Signal(str, str, str)

    def __init__(self, parent=None):
        """OnboardingWindow 초기화"""
        super().__init__(parent)

        self.setWindowTitle("Quill - Welcome")
        self.setModal(True)
        self.setMinimumWidth(500)

        self._setup_ui()
        apply_dark_theme(self)

        logger.debug("OnboardingWindow initialized")

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(24, 24, 24, 24)

        # 환영 메시지
        welcome_label = QLabel("<h2>Welcome to Quill!</h2>")
        welcome_label.setObjectName("titleLabel")
        layout.addWidget(welcome_label)

        desc_label = QLabel(
            "Quill is an AI-powered writing assistant for Windows.\n"
            "Let's set up your OpenAI-compatible API to get started."
        )
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # API 설정 그룹
        api_group = QGroupBox("API Configuration")
        api_layout = QFormLayout()
        api_layout.setSpacing(12)

        # Base URL
        self.input_base_url = QLineEdit()
        self.input_base_url.setPlaceholderText("e.g., http://localhost:8080/v1")
        api_layout.addRow("Base URL:", self.input_base_url)

        # API Key
        self.input_api_key = QLineEdit()
        self.input_api_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.input_api_key.setPlaceholderText("Optional (leave empty if not needed)")
        api_layout.addRow("API Key:", self.input_api_key)

        # Model
        self.input_model = QLineEdit()
        self.input_model.setPlaceholderText("e.g., gemma-3-12b-it")
        api_layout.addRow("Model:", self.input_model)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        # 도움말
        help_label = QLabel(
            "<b>Need help?</b><br>"
            "• For OpenAI: Get your API key from platform.openai.com<br>"
            "• For local LLM: Use your llama.cpp or KoboldCPP server URL<br>"
            "• For Ollama: Use http://localhost:11434/v1 (no API key needed)"
        )
        help_label.setObjectName("subtitleLabel")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # 버튼
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)

        self.btn_continue = QPushButton("Continue")
        self.btn_continue.setObjectName("sendButton")
        self.btn_continue.setDefault(True)
        self.btn_continue.clicked.connect(self._on_continue)
        button_layout.addWidget(self.btn_continue)

        layout.addLayout(button_layout)

        self.setLayout(layout)

        # 포커스를 Base URL 입력란에
        self.input_base_url.setFocus()

    def _on_continue(self):
        """계속 버튼 클릭 시"""
        base_url = self.input_base_url.text().strip()
        api_key = self.input_api_key.text().strip()
        model = self.input_model.text().strip()

        # 유효성 검사
        if not base_url:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Please enter a Base URL."
            )
            self.input_base_url.setFocus()
            return

        if not model:
            QMessageBox.warning(
                self,
                "Invalid Input",
                "Please enter a Model name."
            )
            self.input_model.setFocus()
            return

        # API 키는 선택적 (Ollama 같은 경우)
        if not api_key:
            reply = QMessageBox.question(
                self,
                "No API Key",
                "No API key provided. Continue without API key?\n"
                "(This works for Ollama and some local servers)",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No:
                self.input_api_key.setFocus()
                return

        logger.info(f"Onboarding completed: {base_url}, model: {model}")

        # Signal 발생
        self.setup_completed.emit(base_url, api_key, model)

        # 창 닫기
        self.accept()


# 테스트 코드
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    window = OnboardingWindow()

    # Signal 연결 (테스트)
    def on_setup_completed(base_url, api_key, model):
        print(f"\nSetup completed:")
        print(f"  Base URL: {base_url}")
        print(f"  API Key: {api_key[:10]}..." if api_key else "  API Key: (none)")
        print(f"  Model: {model}")

    window.setup_completed.connect(on_setup_completed)

    window.show()
    sys.exit(app.exec())
