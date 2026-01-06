"""
전역 핫키 관리자

pynput을 사용하여 Windows 전역 핫키를 감지합니다.
"""

import logging
from typing import Optional
from PySide6.QtCore import QObject, Signal

from pynput import keyboard
from pynput.mouse import Controller as MouseController


logger = logging.getLogger(__name__)


class HotkeyManager(QObject):
    """전역 핫키 관리자"""

    # Signal: 핫키가 눌렸을 때 (x, y 마우스 위치)
    hotkey_pressed = Signal(int, int)

    def __init__(self):
        """HotkeyManager 초기화"""
        super().__init__()

        self.listener: Optional[keyboard.GlobalHotKeys] = None
        self.hotkey: str = "<ctrl>+<space>"  # 기본 핫키
        self.is_active: bool = True
        self.mouse = MouseController()

        logger.debug("HotkeyManager initialized")

    def start(self, hotkey: Optional[str] = None):
        """
        핫키 리스닝 시작

        Args:
            hotkey: 핫키 문자열 (예: "<ctrl>+<space>")
                   None이면 현재 핫키 사용
        """
        if hotkey:
            self.hotkey = hotkey

        # 이미 실행 중이면 중지
        if self.listener and self.listener.running:
            self.stop()

        try:
            # GlobalHotKeys 리스너 생성
            self.listener = keyboard.GlobalHotKeys({
                self.hotkey: self._on_hotkey_activated
            })

            self.listener.start()
            logger.info(f"Hotkey listener started: {self.hotkey}")

        except Exception as e:
            logger.error(f"Failed to start hotkey listener: {e}")
            raise RuntimeError(f"Failed to start hotkey listener: {e}") from e

    def stop(self):
        """핫키 리스닝 중지"""
        if self.listener:
            self.listener.stop()
            self.listener = None
            logger.info("Hotkey listener stopped")

    def set_hotkey(self, hotkey: str):
        """
        핫키 변경 (리스너 재시작)

        Args:
            hotkey: 새 핫키 문자열
        """
        logger.info(f"Changing hotkey: {self.hotkey} -> {hotkey}")
        self.hotkey = hotkey

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
        """핫키가 눌렸을 때 콜백"""
        if not self.is_active:
            logger.debug("Hotkey pressed but paused, ignoring")
            return

        try:
            # 마우스 위치 가져오기
            x, y = self.mouse.position

            logger.debug(f"Hotkey activated at position ({x}, {y})")

            # Signal 발생 (Qt 메인 스레드로 전달)
            self.hotkey_pressed.emit(x, y)

        except Exception as e:
            logger.error(f"Error in hotkey callback: {e}")

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
