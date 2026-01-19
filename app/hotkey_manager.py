"""
전역 핫키 관리자

pynput을 사용하여 Windows 전역 핫키를 감지합니다.
"""

import logging
import time
from typing import Optional
from PySide6.QtCore import QObject, Signal

from pynput import keyboard
from pynput.mouse import Controller as MouseController


logger = logging.getLogger(__name__)


class HotkeyManager(QObject):
    """전역 핫키 관리자"""

    # Signal: 핫키가 눌렸을 때 (x, y 마우스 위치)
    hotkey_pressed = Signal(int, int)
    quick_hotkey_pressed = Signal(int, int)  # 빠른 반복 핫키

    def __init__(self):
        """HotkeyManager 초기화"""
        super().__init__()

        self.listener: Optional[keyboard.GlobalHotKeys] = None
        self.hotkey: str = "<ctrl>+<space>"  # 기본 핫키
        self.quick_hotkey: str = ""  # 빠른 반복 핫키 (빈 문자열이면 비활성화)
        self.is_active: bool = True
        self.mouse = MouseController()

        # Quick hotkey가 트리거되면 main hotkey 억제 (충돌 방지)
        self._quick_hotkey_timestamp: float = 0
        self._suppress_duration: float = 0.2  # 200ms

        logger.debug("HotkeyManager initialized")

    def start(self, hotkey: Optional[str] = None, quick_hotkey: Optional[str] = None):
        """
        핫키 리스닝 시작

        Args:
            hotkey: 메인 핫키 문자열 (예: "<ctrl>+<space>")
                   None이면 현재 핫키 사용
            quick_hotkey: 빠른 반복 핫키 문자열 (예: "<ctrl>+<alt>+<space>")
                   None이면 현재 설정 사용, 빈 문자열이면 비활성화
        """
        if hotkey:
            self.hotkey = hotkey
        if quick_hotkey is not None:
            self.quick_hotkey = quick_hotkey

        # 이미 실행 중이면 중지
        if self.listener and self.listener.running:
            self.stop()

        try:
            # 핫키 딕셔너리 구성
            hotkeys_dict = {self.hotkey: self._on_hotkey_activated}
            if self.quick_hotkey:
                hotkeys_dict[self.quick_hotkey] = self._on_quick_hotkey_activated
                logger.info(f"Quick hotkey registered: {self.quick_hotkey}")

            logger.info(f"Registering hotkeys: {list(hotkeys_dict.keys())}")

            # GlobalHotKeys 리스너 생성
            self.listener = keyboard.GlobalHotKeys(hotkeys_dict)

            self.listener.start()
            logger.info(f"Hotkey listener started: main={self.hotkey}, quick={self.quick_hotkey or 'disabled'}")

        except Exception as e:
            logger.error(f"Failed to start hotkey listener: {e}")
            raise RuntimeError(f"Failed to start hotkey listener: {e}") from e

    def stop(self):
        """핫키 리스닝 중지"""
        if self.listener:
            self.listener.stop()
            self.listener = None
            logger.info("Hotkey listener stopped")

    def set_hotkeys(self, hotkey: Optional[str] = None, quick_hotkey: Optional[str] = None):
        """
        핫키 변경 (리스너 재시작)

        Args:
            hotkey: 새 메인 핫키 문자열
            quick_hotkey: 새 빠른 반복 핫키 문자열
        """
        if hotkey:
            logger.info(f"Changing main hotkey: {self.hotkey} -> {hotkey}")
            self.hotkey = hotkey
        if quick_hotkey is not None:
            logger.info(f"Changing quick hotkey: {self.quick_hotkey} -> {quick_hotkey or 'disabled'}")
            self.quick_hotkey = quick_hotkey

        if self.is_active:
            self.start()

    def pause(self):
        """핫키 감지 일시 중지"""
        self.is_active = False
        logger.debug("Hotkey detection paused")

    def resume(self):
        """핫키 감지 재개"""
        self.is_active = True
        logger.debug("Hotkey detection resumed")

    def _on_hotkey_activated(self):
        """메인 핫키가 눌렸을 때 콜백"""
        if not self.is_active:
            logger.debug("Hotkey pressed but paused, ignoring")
            return

        # Quick hotkey가 최근에 눌렸으면 main hotkey 무시 (충돌 방지)
        if time.time() - self._quick_hotkey_timestamp < self._suppress_duration:
            logger.debug("Main hotkey suppressed due to recent quick hotkey")
            return

        try:
            # 마우스 위치 가져오기
            x, y = self.mouse.position

            logger.debug(f"Main hotkey activated at position ({x}, {y})")

            # Signal 발생 (Qt 메인 스레드로 전달)
            self.hotkey_pressed.emit(x, y)

        except Exception as e:
            logger.error(f"Error in hotkey callback: {e}")

    def _on_quick_hotkey_activated(self):
        """빠른 반복 핫키가 눌렸을 때 콜백"""
        # 타임스탬프 기록 (main hotkey 억제용)
        self._quick_hotkey_timestamp = time.time()

        if not self.is_active:
            logger.debug("Quick hotkey pressed but paused, ignoring")
            return

        try:
            # 마우스 위치 가져오기
            x, y = self.mouse.position

            logger.debug(f"Quick hotkey activated at position ({x}, {y})")

            # Signal 발생 (Qt 메인 스레드로 전달)
            self.quick_hotkey_pressed.emit(x, y)

        except Exception as e:
            logger.error(f"Error in quick hotkey callback: {e}")

    def is_running(self) -> bool:
        """
        핫키 리스너가 실행 중인지 확인

        Returns:
            실행 중이면 True
        """
        return self.listener is not None and self.listener.running


# 테스트 코드
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication
    import time

    logging.basicConfig(level=logging.DEBUG)

    print("\n=== Testing HotkeyManager ===\n")

    app = QApplication(sys.argv)

    hotkey_manager = HotkeyManager()

    # Signal 연결
    def on_hotkey_pressed(x, y):
        print(f"\n[Hotkey Pressed!]")
        print(f"  Mouse position: ({x}, {y})")
        print(f"  Press Ctrl+C to exit\n")

    hotkey_manager.hotkey_pressed.connect(on_hotkey_pressed)

    # 핫키 시작
    print("Starting hotkey listener...")
    print(f"  Hotkey: {hotkey_manager.hotkey}")
    print(f"  Press the hotkey to test")
    print(f"  Press Ctrl+C to exit\n")

    hotkey_manager.start()

    try:
        # Qt 이벤트 루프 실행
        sys.exit(app.exec())
    except KeyboardInterrupt:
        print("\n\nStopping hotkey listener...")
        hotkey_manager.stop()
        print("[OK] Test completed!")
