"""
설정 창

API 설정, 단축키 설정 등을 관리합니다.
"""

import json
import logging
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel,
    QLineEdit, QPushButton, QGroupBox, QFormLayout,
    QMessageBox, QTabWidget, QWidget, QComboBox,
    QTextEdit
)
from PySide6.QtCore import Signal

from ui.styles import apply_dark_theme


logger = logging.getLogger(__name__)


class HotkeyEdit(QLineEdit):
    """단축키 입력 위젯 - 직접 텍스트 입력"""

    # pynput 특수 키 목록 (꺾쇠괄호 필요)
    SPECIAL_KEYS = {
        'space', 'enter', 'tab', 'esc', 'backspace', 'delete',
        'insert', 'home', 'end', 'page_up', 'page_down',
        'up', 'down', 'left', 'right',
        'f1', 'f2', 'f3', 'f4', 'f5', 'f6', 'f7', 'f8', 'f9', 'f10', 'f11', 'f12'
    }

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setPlaceholderText("e.g., <ctrl>+<space>, <ctrl>+<shift>+a, <alt>+q")

    def get_key_sequence(self) -> str:
        """
        현재 키 시퀀스 반환 (pynput 형식으로 변환)

        사용자 입력: <ctrl>+<q> 또는 <ctrl>+q
        pynput 형식: <ctrl>+q (일반 문자는 꺾쇠괄호 제거)
        """
        user_input = self.text().strip()
        if not user_input:
            return ""

        # '+' 기준으로 분리
        parts = user_input.split('+')
        converted_parts = []

        for part in parts:
            part = part.strip()

            # 꺾쇠괄호 제거
            if part.startswith('<') and part.endswith('>'):
                key_name = part[1:-1].lower()

                # 수정자 키나 특수 키는 꺾쇠괄호 유지
                if key_name in ('ctrl', 'shift', 'alt', 'cmd') or key_name in self.SPECIAL_KEYS:
                    converted_parts.append(f'<{key_name}>')
                else:
                    # 일반 문자는 꺾쇠괄호 제거
                    converted_parts.append(key_name)
            else:
                # 이미 꺾쇠괄호 없으면 그대로
                converted_parts.append(part.lower())

        return '+'.join(converted_parts)

    def set_key_sequence(self, pynput_sequence: str):
        """키 시퀀스 설정 (표시용으로 변환)"""
        self.setText(pynput_sequence)


class SettingsWindow(QDialog):
    """설정 창"""

    # Signal: 설정 저장 완료
    settings_saved = Signal(dict)

    def __init__(self, config_manager, crypto_manager, prompt_manager=None, parent=None):
        """
        SettingsWindow 초기화

        Args:
            config_manager: ConfigManager 인스턴스
            crypto_manager: CryptoManager 인스턴스
            prompt_manager: PromptManager 인스턴스 (선택적)
            parent: 부모 위젯
        """
        super().__init__(parent)

        self.config_manager = config_manager
        self.crypto_manager = crypto_manager
        self.prompt_manager = prompt_manager

        self.setWindowTitle("Quill - Settings")
        self.setModal(True)
        self.setMinimumWidth(600)
        self.setMinimumHeight(400)

        self._setup_ui()
        self._load_current_settings()
        apply_dark_theme(self)

        logger.debug("SettingsWindow initialized")

    def _setup_ui(self):
        """UI 구성"""
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.setContentsMargins(16, 16, 16, 16)

        # 탭 위젯
        self.tabs = QTabWidget()

        # API 설정 탭
        api_tab = self._create_api_tab()
        self.tabs.addTab(api_tab, "API")

        # 핫키 설정 탭
        hotkey_tab = self._create_hotkey_tab()
        self.tabs.addTab(hotkey_tab, "Hotkey")

        # 프롬프트 설정 탭 (prompt_manager가 있을 때만)
        if self.prompt_manager:
            prompts_tab = self._create_prompts_tab()
            self.tabs.addTab(prompts_tab, "Prompts")

        layout.addWidget(self.tabs)

        # 버튼
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        button_layout.addWidget(self.btn_cancel)

        self.btn_save = QPushButton("Save")
        self.btn_save.setObjectName("sendButton")
        self.btn_save.setDefault(True)
        self.btn_save.clicked.connect(self._on_save)
        button_layout.addWidget(self.btn_save)

        layout.addLayout(button_layout)

        self.setLayout(layout)

    def _create_api_tab(self):
        """API 설정 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)

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
        self.input_api_key.setPlaceholderText("Optional (leave empty to keep current)")
        api_layout.addRow("API Key:", self.input_api_key)

        # Model
        self.input_model = QLineEdit()
        self.input_model.setPlaceholderText("e.g., gemma-3-12b-it")
        api_layout.addRow("Model:", self.input_model)

        # Additional Parameters
        self.input_additional_params = QTextEdit()
        self.input_additional_params.setPlaceholderText(
            'Optional JSON format:\n'
            '{\n'
            '  "reasoning_effort": "high",\n'
            '  "top_p": 0.9\n'
            '}'
        )
        self.input_additional_params.setMaximumHeight(120)
        api_layout.addRow("Additional Params:", self.input_additional_params)

        # Additional Parameters 도움말
        params_help = QLabel(
            "Optional API parameters (reasoning_effort, top_p, etc.)"
        )
        params_help.setObjectName("subtitleLabel")
        api_layout.addRow("", params_help)

        api_group.setLayout(api_layout)
        layout.addWidget(api_group)

        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def _create_hotkey_tab(self):
        """핫키 설정 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)

        # 핫키 설정 그룹
        hotkey_group = QGroupBox("Global Hotkey")
        hotkey_layout = QFormLayout()
        hotkey_layout.setSpacing(12)

        # 핫키 입력
        self.input_hotkey = HotkeyEdit()
        hotkey_layout.addRow("Hotkey:", self.input_hotkey)

        # 도움말
        help_label = QLabel(
            "Enter hotkey combination.\n"
            "Example: <ctrl>+<space>, <ctrl>+<shift>+a, <alt>+q\n"
            "Note: Regular keys (a-z, 0-9) don't need angle brackets"
        )
        help_label.setObjectName("subtitleLabel")
        help_label.setWordWrap(True)
        hotkey_layout.addRow("", help_label)

        hotkey_group.setLayout(hotkey_layout)
        layout.addWidget(hotkey_group)

        layout.addStretch()

        tab.setLayout(layout)
        return tab

    def _create_prompts_tab(self):
        """프롬프트 설정 탭 생성"""
        tab = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)

        # 프롬프트 설정 그룹
        prompts_group = QGroupBox("Prompt Settings")
        prompts_layout = QFormLayout()
        prompts_layout.setSpacing(12)

        # 프롬프트 선택
        self.prompt_combo = QComboBox()
        self.prompt_combo.currentIndexChanged.connect(self._on_prompt_selected)
        prompts_layout.addRow("Select Prompt:", self.prompt_combo)

        # 이름 편집 (custom은 편집 불가)
        self.prompt_name_edit = QLineEdit()
        self.prompt_name_edit.setPlaceholderText("Prompt name...")
        prompts_layout.addRow("Name:", self.prompt_name_edit)

        # Temperature 편집
        self.prompt_temp_edit = QLineEdit()
        self.prompt_temp_edit.setPlaceholderText("e.g., 0.7")
        prompts_layout.addRow("Temperature:", self.prompt_temp_edit)

        # 템플릿 편집
        self.prompt_template_edit = QTextEdit()
        self.prompt_template_edit.setMinimumHeight(150)
        prompts_layout.addRow("Template:", self.prompt_template_edit)

        prompts_group.setLayout(prompts_layout)
        layout.addWidget(prompts_group)

        # 도움말
        help_label = QLabel(
            "Use {{text}} and {{instruction}} as variables.\n"
            "Custom prompt name cannot be changed."
        )
        help_label.setObjectName("subtitleLabel")
        help_label.setWordWrap(True)
        layout.addWidget(help_label)

        # 버튼 레이아웃
        prompt_btn_layout = QHBoxLayout()

        # Reset to Default 버튼
        self.btn_reset_prompt = QPushButton("Reset to Default")
        self.btn_reset_prompt.clicked.connect(self._on_reset_prompt)
        prompt_btn_layout.addWidget(self.btn_reset_prompt)

        prompt_btn_layout.addStretch()

        # Apply Changes 버튼
        self.btn_apply_prompt = QPushButton("Apply Changes")
        self.btn_apply_prompt.clicked.connect(self._on_apply_prompt)
        prompt_btn_layout.addWidget(self.btn_apply_prompt)

        layout.addLayout(prompt_btn_layout)

        layout.addStretch()

        # 프롬프트 로드
        self._load_prompts()

        tab.setLayout(layout)
        return tab

    def _load_prompts(self):
        """프롬프트 목록 로드"""
        if not self.prompt_manager:
            return

        try:
            prompts = self.prompt_manager.prompts

            self.prompt_combo.clear()
            for key, prompt in prompts.items():
                name = prompt.get("name", key)
                self.prompt_combo.addItem(name, key)

            # 첫 번째 항목 자동 선택 (currentIndexChanged가 발생함)

        except Exception as e:
            logger.error(f"Error loading prompts: {e}")

    def _on_prompt_selected(self, index):
        """프롬프트 선택 시"""
        if index < 0 or not self.prompt_manager:
            return

        try:
            prompt_key = self.prompt_combo.itemData(index)
            prompt = self.prompt_manager.prompts.get(prompt_key)

            if prompt:
                # Populate edit fields
                self.prompt_name_edit.setText(prompt.get("name", ""))
                self.prompt_temp_edit.setText(str(prompt.get("temperature", 0.7)))
                self.prompt_template_edit.setPlainText(prompt.get("template", ""))

                # Disable name editing for "custom" prompt
                is_custom = (prompt_key == "custom")
                self.prompt_name_edit.setReadOnly(is_custom)

        except Exception as e:
            logger.error(f"Error displaying prompt: {e}")

    def _on_apply_prompt(self):
        """Apply Changes 버튼 클릭 시 - 현재 프롬프트 저장"""
        if not self._save_current_prompt():
            return

        QMessageBox.information(
            self,
            "Applied",
            "Prompt changes applied."
        )

    def _save_current_prompt(self) -> bool:
        """현재 프롬프트 저장 (검증 포함). 성공 시 True 반환."""
        if not self.prompt_manager:
            return True  # prompt_manager 없으면 그냥 통과

        try:
            # Get current selected prompt
            current_index = self.prompt_combo.currentIndex()
            if current_index < 0:
                return True  # 선택된 프롬프트 없으면 통과

            prompt_key = self.prompt_combo.itemData(current_index)

            # Get new values
            new_name = self.prompt_name_edit.text().strip()
            temp_str = self.prompt_temp_edit.text().strip()
            new_template = self.prompt_template_edit.toPlainText()

            # Validate name
            if not new_name and prompt_key != "custom":
                QMessageBox.warning(
                    self,
                    "Invalid Name",
                    "Prompt name cannot be empty."
                )
                return False

            # Validate template
            if not new_template.strip():
                QMessageBox.warning(
                    self,
                    "Invalid Template",
                    "Template cannot be empty."
                )
                return False

            # Validate and parse temperature
            try:
                new_temp = float(temp_str)
                if not (0.0 <= new_temp <= 2.0):
                    raise ValueError("Temperature must be between 0.0 and 2.0")
            except ValueError as e:
                QMessageBox.warning(
                    self,
                    "Invalid Temperature",
                    f"Please enter a valid temperature value (0.0 - 2.0).\n{e}"
                )
                return False

            # Update prompt
            self.prompt_manager.update_prompt(
                prompt_key,
                name=new_name if prompt_key != "custom" else None,
                template=new_template,
                temperature=new_temp
            )

            # Save to file
            self.prompt_manager.save()

            # Update combo display (only if name changed and not custom)
            if prompt_key != "custom" and new_name:
                self.prompt_combo.setItemText(current_index, new_name)

            logger.info(f"Prompt {prompt_key} saved successfully")
            return True

        except Exception as e:
            logger.error(f"Error saving prompt: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save prompt: {e}"
            )
            return False

    def _on_reset_prompt(self):
        """Reset to Default 버튼 클릭 시"""
        if not self.prompt_manager:
            return

        try:
            current_index = self.prompt_combo.currentIndex()
            if current_index < 0:
                return

            prompt_key = self.prompt_combo.itemData(current_index)

            # 기본 프롬프트에 없는 경우 (사용자 추가 프롬프트)
            if prompt_key not in self.prompt_manager.default_prompts:
                QMessageBox.warning(
                    self,
                    "Cannot Reset",
                    "This is a custom prompt without a default version."
                )
                return

            # 확인 대화상자 (표시 이름 사용, 긴 이름은 픽셀 기반 truncate)
            prompt_name = self.prompt_combo.currentText()
            max_width = 80
            fm = self.fontMetrics()
            if fm.horizontalAdvance(prompt_name) > max_width:
                while fm.horizontalAdvance(prompt_name + "...") > max_width and len(prompt_name) > 0:
                    prompt_name = prompt_name[:-1]
                prompt_name = prompt_name + "..."

            reply = QMessageBox.question(
                self,
                "Reset to Default",
                f"Reset '{prompt_name}' to default?\n\nThis will discard your changes.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
            )

            if reply != QMessageBox.StandardButton.Yes:
                return

            # 기본값으로 리셋
            self.prompt_manager.reset_prompt(prompt_key)
            self.prompt_manager.save()

            # UI 업데이트
            default_prompt = self.prompt_manager.default_prompts[prompt_key]
            self.prompt_name_edit.setText(default_prompt.get("name", ""))
            self.prompt_temp_edit.setText(str(default_prompt.get("temperature", 0.7)))
            self.prompt_template_edit.setPlainText(default_prompt.get("template", ""))

            # 콤보박스 이름 업데이트
            self.prompt_combo.setItemText(current_index, default_prompt.get("name", prompt_key))

            logger.info(f"Prompt {prompt_key} reset to default")

            QMessageBox.information(
                self,
                "Reset Complete",
                "Prompt has been reset to default."
            )

        except Exception as e:
            logger.error(f"Error resetting prompt: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to reset prompt: {e}"
            )

    def _load_current_settings(self):
        """현재 설정 로드"""
        try:
            config = self.config_manager.get_all()

            # API 설정
            self.input_base_url.setText(
                self.config_manager.get("api.base_url", "")
            )
            self.input_model.setText(
                self.config_manager.get("api.model", "")
            )
            # API 키는 보안상 표시하지 않음

            # Additional Parameters 로드
            additional_params = self.config_manager.get("api.additional_params", {})
            if additional_params:
                self.input_additional_params.setPlainText(
                    json.dumps(additional_params, indent=2, ensure_ascii=False)
                )

            # 핫키 설정
            hotkey = self.config_manager.get("hotkey.key", "<ctrl>+<space>")
            self.input_hotkey.set_key_sequence(hotkey)

            logger.debug("Current settings loaded")

        except Exception as e:
            logger.error(f"Error loading settings: {e}")
            QMessageBox.warning(
                self,
                "Error",
                f"Failed to load settings: {e}"
            )

    def _on_save(self):
        """저장 버튼 클릭 시"""
        try:
            # 프롬프트 저장 (Prompts 탭이 있는 경우)
            if self.prompt_manager and not self._save_current_prompt():
                return

            # API 설정 저장
            base_url = self.input_base_url.text().strip()
            api_key = self.input_api_key.text().strip()
            model = self.input_model.text().strip()

            if not base_url or not model:
                QMessageBox.warning(
                    self,
                    "Invalid Input",
                    "Please fill in Base URL and Model."
                )
                return

            # Additional Parameters 파싱
            params_text = self.input_additional_params.toPlainText().strip()
            additional_params = {}
            if params_text:
                try:
                    additional_params = json.loads(params_text)
                    if not isinstance(additional_params, dict):
                        raise ValueError("Must be a JSON object")
                except (json.JSONDecodeError, ValueError) as e:
                    QMessageBox.warning(
                        self,
                        "Invalid JSON",
                        f"Additional Parameters must be valid JSON object.\n\nError: {e}"
                    )
                    return

            # ConfigManager에 저장
            self.config_manager.set("api.base_url", base_url)
            self.config_manager.set("api.model", model)
            self.config_manager.set("api.additional_params", additional_params)

            # API 키는 입력된 경우에만 업데이트
            if api_key:
                self.config_manager.set_api_key(api_key)

            # 핫키 저장
            hotkey = self.input_hotkey.get_key_sequence()
            if hotkey:
                # Validate hotkey has at least one modifier
                if not any(mod in hotkey for mod in ['<ctrl>', '<shift>', '<alt>']):
                    QMessageBox.warning(
                        self,
                        "Invalid Hotkey",
                        "Hotkey must include at least one modifier key (Ctrl, Shift, or Alt)."
                    )
                    return

                # Validate against critical system hotkeys only
                critical_hotkeys = [
                    '<alt>+<f4>',  # Close window
                    '<ctrl>+<alt>+<delete>',  # Security screen
                    '<ctrl>+<shift>+<esc>',  # Task Manager
                ]

                if hotkey.lower() in critical_hotkeys:
                    QMessageBox.warning(
                        self,
                        "Reserved Hotkey",
                        f"'{hotkey}' is a critical system hotkey and cannot be used.\n\n"
                        "Please choose a different combination."
                    )
                    return

                self.config_manager.set("hotkey.key", hotkey)

            # 파일에 저장
            self.config_manager.save()

            logger.info("Settings saved successfully")

            # Signal 발생
            self.settings_saved.emit(self.config_manager.get_all())

            QMessageBox.information(
                self,
                "Settings Saved",
                "Your settings have been saved successfully."
            )

            # 창 닫기
            self.accept()

        except Exception as e:
            logger.error(f"Error saving settings: {e}")
            QMessageBox.critical(
                self,
                "Error",
                f"Failed to save settings: {e}"
            )


# 테스트 코드
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    from core.config_manager import ConfigManager
    from core.crypto_manager import CryptoManager

    logging.basicConfig(level=logging.DEBUG)

    app = QApplication(sys.argv)

    # ConfigManager 생성 (테스트용)
    config = ConfigManager()
    if not config.is_configured():
        config.create_default_config()

    crypto = CryptoManager()

    window = SettingsWindow(config, crypto)

    # Signal 연결 (테스트)
    def on_settings_saved(settings):
        print("\nSettings saved:")
        print(f"  Base URL: {settings.get('api', {}).get('base_url')}")
        print(f"  Model: {settings.get('api', {}).get('model')}")
        print(f"  Hotkey: {settings.get('hotkey', {}).get('key')}")

    window.settings_saved.connect(on_settings_saved)

    window.show()
    sys.exit(app.exec())
