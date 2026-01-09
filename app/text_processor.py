"""
텍스트 처리기

선택된 텍스트를 추출하고 AI 응답으로 대체합니다.
Worker 패턴: 매 작업마다 새 QThread 생성으로 안정성 확보.
"""

import time
import logging
import threading
from typing import Optional

import pyperclip
from pynput.keyboard import Controller, Key
from PySide6.QtCore import QObject, QThread, Signal, Slot


logger = logging.getLogger(__name__)


class TextWorker(QObject):
    """텍스트 작업 Worker (QThread에서 실행)"""

    # Signals
    text_extracted = Signal(str)
    text_replaced = Signal()
    finished = Signal()

    def __init__(self):
        super().__init__()
        self.keyboard = Controller()
        self.operation: Optional[str] = None
        self.replacement_text: str = ""
        self.sleep_duration: float = 0.1

    @Slot()
    def run(self):
        """작업 실행"""
        try:
            if self.operation == 'extract':
                self._extract()
            elif self.operation == 'replace':
                self._replace()
        except Exception as e:
            logger.error(f"Error in TextWorker: {e}")
        finally:
            self.finished.emit()

    def _extract(self):
        """텍스트 추출 (Ctrl+C 시뮬레이션)"""
        try:
            # 1. 클립보드 백업
            original_clipboard = pyperclip.paste()
            logger.debug(f"Clipboard backed up (length: {len(original_clipboard)})")

            # 2. Ctrl+C 시뮬레이션
            with self.keyboard.pressed(Key.ctrl):
                self.keyboard.press('c')
                self.keyboard.release('c')

            # 3. 클립보드 업데이트 대기
            time.sleep(self.sleep_duration)

            # 4. 클립보드에서 텍스트 가져오기
            selected_text = pyperclip.paste()

            # 5. 클립보드 복원
            pyperclip.copy(original_clipboard)

            # 6. 텍스트가 변경되었는지 확인
            if selected_text != original_clipboard:
                logger.info(f"Text extracted successfully (length: {len(selected_text)})")
                self.text_extracted.emit(selected_text)
            else:
                logger.debug("No text selected (clipboard unchanged)")
                self.text_extracted.emit("")

        except Exception as e:
            logger.error(f"Error extracting text: {e}")
            self.text_extracted.emit("")

    def _replace(self):
        """텍스트 대체 (Ctrl+V 시뮬레이션)"""
        try:
            # 1. 클립보드 백업
            original_clipboard = pyperclip.paste()
            logger.debug("Clipboard backed up for replacement")

            # 2. 새 텍스트를 클립보드에 복사 (끝의 공백/줄바꿈 제거)
            cleaned_text = self.replacement_text.rstrip()
            pyperclip.copy(cleaned_text)
            logger.debug(f"New text copied to clipboard (length: {len(cleaned_text)})")

            # 3. 짧은 대기 (클립보드 업데이트 보장)
            time.sleep(0.05)

            # 4. Ctrl+V 시뮬레이션
            with self.keyboard.pressed(Key.ctrl):
                self.keyboard.press('v')
                self.keyboard.release('v')

            # 5. 붙여넣기 완료 대기
            time.sleep(0.05)

            # 6. 클립보드 복원
            pyperclip.copy(original_clipboard)
            logger.info("Text replaced successfully")

            # 7. Signal 발생
            self.text_replaced.emit()

        except Exception as e:
            logger.error(f"Error replacing text: {e}")


class TextProcessor(QObject):
    """텍스트 처리 매니저 - 매 작업마다 새 Worker/Thread 생성"""

    # 외부로 전달하는 Signals (기존 API 유지)
    text_extracted = Signal(str)
    text_replaced = Signal()

    def __init__(self):
        super().__init__()
        self._thread: Optional[QThread] = None
        self._worker: Optional[TextWorker] = None
        self._lock = threading.Lock()

        # 워밍업: 클립보드 접근 초기화 (첫 호출 지연 제거)
        try:
            pyperclip.paste()
        except Exception:
            pass

        logger.debug("TextProcessor initialized")

    def _cleanup_previous(self):
        """이전 작업 정리"""
        if self._thread is not None:
            if self._thread.isRunning():
                self._thread.quit()
                self._thread.wait(1000)  # 1초 타임아웃
            self._thread.deleteLater()
            self._thread = None

        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _start_operation(self, operation: str, replacement_text: str = ""):
        """새 작업 시작"""
        with self._lock:
            self._cleanup_previous()

            # 새 Worker와 Thread 생성
            self._worker = TextWorker()
            self._thread = QThread()

            # Worker 설정
            self._worker.operation = operation
            self._worker.replacement_text = replacement_text

            # Worker를 Thread로 이동
            self._worker.moveToThread(self._thread)

            # Signal 연결
            self._thread.started.connect(self._worker.run)
            self._worker.text_extracted.connect(self._on_text_extracted)
            self._worker.text_replaced.connect(self._on_text_replaced)
            self._worker.finished.connect(self._thread.quit)

            # Thread 시작
            self._thread.start()

    @Slot(str)
    def _on_text_extracted(self, text: str):
        """Worker에서 추출 완료 시 외부로 전달"""
        self.text_extracted.emit(text)

    @Slot()
    def _on_text_replaced(self):
        """Worker에서 대체 완료 시 외부로 전달"""
        self.text_replaced.emit()

    def extract_selected_text(self):
        """선택된 텍스트 추출 (Ctrl+C 시뮬레이션)"""
        self._start_operation('extract')

    def replace_text(self, new_text: str):
        """텍스트 대체 (Ctrl+V 시뮬레이션)"""
        self._start_operation('replace', new_text)

    def cleanup(self):
        """리소스 정리"""
        with self._lock:
            self._cleanup_previous()
        logger.debug("TextProcessor cleaned up")
