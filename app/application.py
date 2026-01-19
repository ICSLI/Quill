"""
Quill 메인 애플리케이션

모든 컴포넌트를 통합하고 전체 워크플로우를 조율합니다.
"""

import logging
import sys
import threading
from pathlib import Path

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Slot, Signal
from PySide6.QtGui import QIcon

# Core modules
from core.config_manager import ConfigManager
from core.crypto_manager import CryptoManager
from core.ai_provider import OAICompatibleProvider
from core.prompt_manager import PromptManager

# App modules
from app.hotkey_manager import HotkeyManager
from app.text_processor import TextProcessor
from app.tray_manager import TrayManager

# UI modules
from ui.onboarding_window import OnboardingWindow
from ui.settings_window import SettingsWindow
from ui.popup_window import PopupWindow


logger = logging.getLogger(__name__)


class QuillApp(QApplication):
    """Quill 메인 애플리케이션 클래스"""

    # Signal: 백그라운드 스레드에서 에러 발생 시
    error_occurred = Signal(str, str)

    # Signal: 스레드 안전한 텍스트 교체
    _replace_text_signal = Signal(str)

    def __init__(self, argv):
        """QuillApp 초기화"""
        super().__init__(argv)

        # 마지막 창이 닫혀도 앱 종료 안 함 (트레이 앱)
        self.setQuitOnLastWindowClosed(False)

        # 애플리케이션 아이콘 설정 (타이틀바, 태스크바)
        self._set_app_icon()

        logger.info("Quill application starting...")

        # 매니저 초기화
        self.config_manager = ConfigManager()
        self.crypto_manager = CryptoManager()
        self.ai_provider = OAICompatibleProvider()
        self.prompt_manager = PromptManager()

        self.hotkey_manager = HotkeyManager()
        self.text_processor = TextProcessor()
        self.tray_manager = TrayManager()

        # UI 윈도우
        self.onboarding_window = None
        self.settings_window = None
        self.popup_window = None

        # 상태
        self.current_text = ""  # 현재 선택된 텍스트

        # 빠른 반복 실행용 마지막 액션 저장
        self._last_prompt_key: str = ""
        self._last_instruction: str = ""
        self._quick_mode: bool = False  # 빠른 실행 모드 플래그
        self._extraction_in_progress: bool = False  # 텍스트 추출 진행 중 플래그

        # AI 요청 동기화
        self._ai_request_lock = threading.Lock()
        self._ai_request_in_progress = False

        # Signal/Slot 연결
        self._connect_signals()

        # 첫 실행 확인
        if not self.config_manager.is_configured():
            logger.info("First run detected, showing onboarding")
            self._show_onboarding()
        else:
            logger.info("Configuration found, starting application")
            self._start_app()

    def _set_app_icon(self):
        """애플리케이션 아이콘 설정"""
        # 아이콘 경로 찾기
        project_root = Path(__file__).parent.parent
        icon_path = project_root / "resources" / "icon.ico"

        # PyInstaller 빌드 환경에서는 _internal 폴더 확인
        if not icon_path.exists():
            icon_path = project_root / "_internal" / "resources" / "icon.ico"

        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))
            logger.debug(f"Application icon set: {icon_path}")
        else:
            logger.warning(f"Icon file not found: {icon_path}")

    def _connect_signals(self):
        """Signal/Slot 연결"""
        # Hotkey Manager
        self.hotkey_manager.hotkey_pressed.connect(self._on_hotkey_pressed)
        self.hotkey_manager.quick_hotkey_pressed.connect(self._on_quick_hotkey_pressed)

        # Text Processor
        self.text_processor.text_extracted.connect(self._on_text_extracted)
        self.text_processor.text_replaced.connect(self._on_text_replaced)

        # Tray Manager
        self.tray_manager.settings_requested.connect(self._show_settings)
        self.tray_manager.pause_toggled.connect(self._on_pause_toggled)
        self.tray_manager.quit_requested.connect(self._on_quit_requested)

        # Error handling
        self.error_occurred.connect(self._show_error_dialog)

        # 스레드 안전한 텍스트 교체
        self._replace_text_signal.connect(self._do_replace_text)

        logger.debug("All signals connected")

    def _show_onboarding(self):
        """온보딩 창 표시"""
        self.onboarding_window = OnboardingWindow()
        self.onboarding_window.setup_completed.connect(self._on_onboarding_completed)
        self.onboarding_window.rejected.connect(self._on_onboarding_cancelled)
        self.onboarding_window.show()

    @Slot()
    def _on_onboarding_cancelled(self):
        """온보딩 취소 시 앱 종료"""
        logger.info("Onboarding cancelled, quitting application")
        self.quit()

    @Slot(str, str, str)
    def _on_onboarding_completed(self, base_url: str, api_key: str, model: str):
        """
        온보딩 완료 시

        Args:
            base_url: API base URL
            api_key: API 키
            model: 모델 이름
        """
        try:
            # 설정 저장
            self.config_manager.create_default_config()
            self.config_manager.set("api.base_url", base_url)
            self.config_manager.set("api.model", model)
            if api_key:
                self.config_manager.set_api_key(api_key)
            self.config_manager.save()

            logger.info("Onboarding completed, configuration saved")

            # 앱 시작
            self._start_app()

        except Exception as e:
            logger.error(f"Error completing onboarding: {e}")
            QMessageBox.critical(
                None,
                "Error",
                f"Failed to save configuration: {e}"
            )
            self.quit()

    def _start_app(self):
        """애플리케이션 시작"""
        try:
            # 설정 로드
            self.config_manager.load()

            # AI Provider 설정
            base_url = self.config_manager.get("api.base_url")
            api_key = self.config_manager.get_api_key()
            model = self.config_manager.get("api.model")

            self.ai_provider.configure(base_url, api_key, model)
            logger.info("AI provider configured")

            # 핫키 시작
            hotkey = self.config_manager.get("hotkey.key", "<ctrl>+<space>")
            quick_hotkey = self.config_manager.get("hotkey.quick_key", "")
            self.hotkey_manager.start(hotkey, quick_hotkey)
            logger.info(f"Hotkey started: main={hotkey}, quick={quick_hotkey or 'disabled'}")

            # 트레이 아이콘 생성
            self.tray_manager.create_tray_icon()
            # 시작 알림 제거 (조용한 시작)

            # 팝업 윈도우 미리 생성 (첫 호출 지연 방지)
            self._create_popup_window()

            logger.info("Quill application started successfully")

        except Exception as e:
            logger.error(f"Error starting application: {e}")
            QMessageBox.critical(
                None,
                "Error",
                f"Failed to start application: {e}\n\nPlease check your configuration."
            )
            self.quit()

    @Slot(int, int)
    def _on_hotkey_pressed(self, x: int, y: int):
        """
        메인 핫키가 눌렸을 때

        Args:
            x: 마우스 X 좌표
            y: 마우스 Y 좌표
        """
        # AI 요청 또는 텍스트 추출 진행 중이면 무시
        if self._ai_request_in_progress:
            logger.debug("AI request in progress, ignoring hotkey")
            return
        if self._extraction_in_progress:
            logger.debug("Extraction in progress, ignoring main hotkey")
            return

        logger.debug(f"Main hotkey pressed at ({x}, {y})")

        # 일반 모드로 텍스트 추출
        self._quick_mode = False
        self._extraction_in_progress = True
        self.text_processor.extract_selected_text()

        # 참고: 텍스트가 추출되면 _on_text_extracted()가 호출됨

    @Slot(int, int)
    def _on_quick_hotkey_pressed(self, x: int, y: int):
        """
        빠른 반복 핫키가 눌렸을 때

        Args:
            x: 마우스 X 좌표
            y: 마우스 Y 좌표
        """
        # AI 요청 진행 중이면 무시
        if self._ai_request_in_progress:
            logger.debug("AI request in progress, ignoring quick hotkey")
            return

        # 이전 액션이 없으면 일반 모드로 팝업 표시
        if not self._last_prompt_key:
            logger.debug("No previous action, falling back to normal popup")
            self._quick_mode = False
            self._extraction_in_progress = True
            self.text_processor.extract_selected_text()
            return

        # 프롬프트가 여전히 존재하는지 확인
        if not self.prompt_manager.get_prompt_info(self._last_prompt_key):
            logger.warning(f"Previous prompt '{self._last_prompt_key}' no longer exists")
            self.tray_manager.show_message(
                "Quick Repeat",
                f"Previous prompt '{self._last_prompt_key}' no longer exists."
            )
            self._last_prompt_key = ""
            return

        logger.debug(f"Quick hotkey pressed at ({x}, {y}), repeating: {self._last_prompt_key}")

        # 빠른 실행 모드 설정
        self._quick_mode = True

        # 이미 추출 진행 중이면 해당 추출 결과를 quick mode로 사용
        if self._extraction_in_progress:
            logger.debug("Extraction already in progress, will use its result in quick mode")
            return

        # 새로 추출 시작
        self._extraction_in_progress = True
        self.text_processor.extract_selected_text()

        # 참고: 텍스트가 추출되면 _on_text_extracted()가 호출됨

    def _create_popup_window(self):
        """팝업 윈도우 생성 및 워밍업"""
        if self.popup_window is not None:
            return

        self.popup_window = PopupWindow()
        self.popup_window.action_requested.connect(self._on_action_requested)

        # 워밍업: 투명 상태로 show/hide하여 렌더링 파이프라인 초기화
        self.popup_window.setWindowOpacity(0)
        self.popup_window.show()
        self.processEvents()
        self.popup_window.hide()
        self.popup_window.setWindowOpacity(1)

        logger.debug("Popup window pre-created")

    @Slot(str)
    def _on_text_extracted(self, text: str):
        """
        텍스트 추출 완료 시

        Args:
            text: 추출된 텍스트
        """
        # 추출 완료 플래그 리셋
        self._extraction_in_progress = False

        if not text:
            logger.debug("No text selected, ignoring hotkey")
            self._quick_mode = False  # 플래그 리셋
            return

        logger.debug(f"Text extracted (length: {len(text)}), quick_mode={self._quick_mode}")
        self.current_text = text

        # 빠른 실행 모드: 팝업 없이 바로 AI 호출
        if self._quick_mode:
            self._quick_mode = False  # 플래그 리셋
            logger.debug(f"Quick mode: executing {self._last_prompt_key}")
            self._on_action_requested(self._last_prompt_key, text, self._last_instruction)
            return

        # 일반 모드: 팝업 표시
        # 팝업이 없으면 생성 (앱 시작 시 생성되지 않은 경우 대비)
        if self.popup_window is None:
            self._create_popup_window()

        # 마우스 위치에 팝업 표시
        from PySide6.QtGui import QCursor
        cursor_pos = QCursor.pos()
        self.popup_window.show_at_position(cursor_pos.x(), cursor_pos.y(), text)

    @Slot(str, str, str)
    def _on_action_requested(self, prompt_key: str, text: str, instruction: str):
        """
        사용자가 작업을 요청했을 때

        Args:
            prompt_key: 프롬프트 키
            text: 선택된 텍스트
            instruction: 사용자 지시사항
        """
        # 중복 요청 방지
        with self._ai_request_lock:
            if self._ai_request_in_progress:
                logger.warning("AI request already in progress, ignoring")
                return
            self._ai_request_in_progress = True

        # 마지막 액션 저장 (빠른 반복 실행용)
        self._last_prompt_key = prompt_key
        self._last_instruction = instruction

        logger.info(f"Action requested: {prompt_key}")

        # 별도 스레드에서 AI 호출
        threading.Thread(
            target=self._process_ai_request,
            args=(prompt_key, text, instruction),
            daemon=True
        ).start()

    def _process_ai_request(self, prompt_key: str, text: str, instruction: str):
        """
        AI 요청 처리 (별도 스레드)

        Args:
            prompt_key: 프롬프트 키
            text: 선택된 텍스트
            instruction: 사용자 지시사항
        """
        try:
            # 프롬프트 생성
            messages = self.prompt_manager.get_messages(prompt_key, text, instruction)
            temperature = self.prompt_manager.get_temperature(prompt_key)

            # 추가 파라미터 가져오기
            additional_params = self.config_manager.get("api.additional_params", {})

            logger.debug(f"Calling AI: {len(messages)} messages, temp={temperature}")

            # AI 호출
            response = self.ai_provider.complete(
                messages, temperature, None, additional_params
            )

            logger.info(f"AI response received (length: {len(response)})")

            # Signal로 메인 스레드에서 텍스트 교체 (스레드 안전)
            self._replace_text_signal.emit(response)

        except Exception as e:
            logger.error(f"Error processing AI request: {e}", exc_info=True)
            # Signal로 메인 스레드에 에러 전달
            self.error_occurred.emit(
                "AI Request Failed",
                f"Failed to process AI request:\n\n{type(e).__name__}: {e}\n\nPlease check your API configuration."
            )
        finally:
            with self._ai_request_lock:
                self._ai_request_in_progress = False

    @Slot(str)
    def _do_replace_text(self, response: str):
        """메인 스레드에서 텍스트 교체 수행"""
        self.text_processor.replace_text(response)

    @Slot()
    def _on_text_replaced(self):
        """텍스트 대체 완료 시"""
        logger.info("Text replacement completed")
        # 알림 제거 (불필요한 UX)

    def _show_settings(self):
        """설정 창 표시"""
        logger.debug("Showing settings window")

        # 기존 창 정리
        if self.settings_window is not None:
            try:
                self.settings_window.settings_saved.disconnect(self._on_settings_saved)
            except RuntimeError:
                pass
            self.settings_window.close()
            self.settings_window.deleteLater()
            self.settings_window = None

        # 새 창 생성
        self.settings_window = SettingsWindow(
            self.config_manager,
            self.crypto_manager,
            self.prompt_manager
        )
        self.settings_window.settings_saved.connect(self._on_settings_saved)
        self.settings_window.show()

    @Slot(dict)
    def _on_settings_saved(self, settings: dict):
        """
        설정 저장 완료 시

        Args:
            settings: 저장된 설정 딕셔너리
        """
        logger.info("Settings saved, reloading configuration")

        try:
            # AI Provider 재설정
            base_url = self.config_manager.get("api.base_url")
            api_key = self.config_manager.get_api_key()
            model = self.config_manager.get("api.model")

            self.ai_provider.configure(base_url, api_key, model)

            # 핫키 재시작
            hotkey = self.config_manager.get("hotkey.key", "<ctrl>+<space>")
            quick_hotkey = self.config_manager.get("hotkey.quick_key", "")
            self.hotkey_manager.set_hotkeys(hotkey, quick_hotkey)

            logger.info("Configuration reloaded successfully")

        except Exception as e:
            logger.error(f"Error reloading configuration: {e}")
            QMessageBox.warning(
                None,
                "Warning",
                f"Settings saved but failed to reload:\n{e}\n\nPlease restart Quill."
            )

    @Slot(bool)
    def _on_pause_toggled(self, paused: bool):
        """
        일시 중지 토글 시

        Args:
            paused: True면 일시 중지, False면 재개
        """
        if paused:
            self.hotkey_manager.pause()
            logger.info("Application paused")
        else:
            self.hotkey_manager.resume()
            logger.info("Application resumed")

    def _on_quit_requested(self):
        """종료 요청 시"""
        logger.info("Quit requested")

        reply = QMessageBox.question(
            None,
            "Quit Quill",
            "Are you sure you want to quit Quill?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )

        if reply == QMessageBox.StandardButton.Yes:
            logger.info("Quitting application - performing cleanup")

            # 1. Hotkey 리스너 중지
            self.hotkey_manager.stop()

            # 2. AI Provider 클라이언트 닫기
            self.ai_provider.close()

            # 3. 트레이 숨기기
            self.tray_manager.hide()

            # 4. Popup 창 정리
            if self.popup_window is not None:
                try:
                    self.popup_window.action_requested.disconnect(self._on_action_requested)
                except RuntimeError:
                    pass
                self.popup_window.close()
                self.popup_window.deleteLater()
                self.popup_window = None

            # 5. Settings 창 정리
            if self.settings_window is not None:
                try:
                    self.settings_window.settings_saved.disconnect(self._on_settings_saved)
                except RuntimeError:
                    pass
                self.settings_window.close()
                self.settings_window.deleteLater()
                self.settings_window = None

            # 6. Onboarding 창 정리
            if self.onboarding_window is not None:
                self.onboarding_window.close()
                self.onboarding_window.deleteLater()
                self.onboarding_window = None

            # 7. TextProcessor 정리
            self.text_processor.cleanup()

            logger.info("Cleanup complete, exiting")
            self.quit()

    @Slot(str, str)
    def _show_error_dialog(self, title: str, message: str):
        """
        에러 다이얼로그 표시 (메인 스레드에서)

        Args:
            title: 에러 제목
            message: 에러 메시지
        """
        QMessageBox.critical(None, title, message)


# 테스트용 진입점 (실제로는 main.py에서 실행)
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    app = QuillApp(sys.argv)
    sys.exit(app.exec())
