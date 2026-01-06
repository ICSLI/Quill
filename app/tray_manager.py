"""
시스템 트레이 관리자

Windows 시스템 트레이 아이콘과 메뉴를 관리합니다.
"""

import logging
from pathlib import Path
from typing import Optional

from PySide6.QtWidgets import QSystemTrayIcon, QMenu
from PySide6.QtGui import QIcon, QAction, QPixmap, QPainter, QColor, QFont
from PySide6.QtCore import QObject, Signal, Qt


logger = logging.getLogger(__name__)


class TrayManager(QObject):
    """시스템 트레이 관리자"""

    # Signals
    settings_requested = Signal()
    pause_toggled = Signal(bool)  # True: paused, False: resumed
    quit_requested = Signal()

    def __init__(self, parent=None):
        """
        TrayManager 초기화

        Args:
            parent: 부모 QObject
        """
        super().__init__(parent)

        self.tray_icon: Optional[QSystemTrayIcon] = None
        self.tray_menu: Optional[QMenu] = None
        self.is_paused: bool = False

        # 액션들
        self.action_settings: Optional[QAction] = None
        self.action_pause: Optional[QAction] = None
        self.action_quit: Optional[QAction] = None

        logger.debug("TrayManager initialized")

    def _create_default_icon(self) -> QIcon:
        """
        기본 아이콘 생성 (텍스트 기반)

        Returns:
            QIcon 객체
        """
        # 32x32 픽셀맵 생성
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)

        # 그리기
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # 배경 원
        painter.setBrush(QColor("#007ACC"))  # VS Code 블루
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(2, 2, 28, 28)

        # 텍스트 "Q"
        painter.setPen(QColor("#FFFFFF"))
        font = QFont("Arial", 16, QFont.Weight.Bold)
        painter.setFont(font)
        painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, "Q")

        painter.end()

        return QIcon(pixmap)

    def create_tray_icon(self, icon_path: Optional[str] = None):
        """
        트레이 아이콘 생성

        Args:
            icon_path: 아이콘 파일 경로 (기본값: resources/icon.ico)
        """
        # 기존 리소스 정리 (재호출 시 누수 방지)
        if self.tray_icon is not None:
            self.tray_icon.hide()
            self.tray_icon.setContextMenu(None)
            self.tray_icon.deleteLater()
            self.tray_icon = None

        if self.tray_menu is not None:
            self.tray_menu.deleteLater()
            self.tray_menu = None

        # 액션 참조 초기화
        self.action_settings = None
        self.action_pause = None
        self.action_quit = None

        if icon_path is None:
            # 프로젝트 루트 기준 resources/icon.ico
            project_root = Path(__file__).parent.parent
            icon_path = project_root / "resources" / "icon.ico"

        # 아이콘 파일이 없으면 기본 아이콘 생성
        if not Path(icon_path).exists():
            logger.warning(f"Icon file not found: {icon_path}, creating default icon")
            icon = self._create_default_icon()
        else:
            icon = QIcon(str(icon_path))

        # 트레이 아이콘 생성
        self.tray_icon = QSystemTrayIcon(icon)
        self.tray_icon.setToolTip("Quill - AI Writing Assistant")

        # 메뉴 생성
        self._create_menu()

        # 트레이 아이콘 표시
        self.tray_icon.show()

        logger.info("Tray icon created and shown")

    def _create_menu(self):
        """트레이 메뉴 생성"""
        # Parent를 명시적으로 지정하여 가비지 컬렉션 방지
        self.tray_menu = QMenu()

        # Settings 액션 (parent 지정)
        self.action_settings = QAction("Settings", self.tray_menu)
        self.action_settings.triggered.connect(self._on_settings_clicked)
        self.tray_menu.addAction(self.action_settings)

        # 구분선
        self.tray_menu.addSeparator()

        # Pause/Resume 액션 (parent 지정)
        self.action_pause = QAction("Pause", self.tray_menu)
        self.action_pause.triggered.connect(self._on_pause_clicked)
        self.tray_menu.addAction(self.action_pause)

        # 구분선
        self.tray_menu.addSeparator()

        # Quit 액션 (parent 지정)
        self.action_quit = QAction("Quit", self.tray_menu)
        self.action_quit.triggered.connect(self._on_quit_clicked)
        self.tray_menu.addAction(self.action_quit)

        # 메뉴 설정
        self.tray_icon.setContextMenu(self.tray_menu)

        logger.debug("Tray menu created with actions")

    def _on_settings_clicked(self):
        """Settings 메뉴 클릭 시"""
        logger.debug("Settings menu clicked")
        self.settings_requested.emit()

    def _on_pause_clicked(self):
        """Pause/Resume 메뉴 클릭 시"""
        self.is_paused = not self.is_paused

        if self.is_paused:
            self.action_pause.setText("Resume")
            logger.info("Application paused")
        else:
            self.action_pause.setText("Pause")
            logger.info("Application resumed")

        self.pause_toggled.emit(self.is_paused)

    def _on_quit_clicked(self):
        """Quit 메뉴 클릭 시"""
        logger.info("Quit requested")
        self.quit_requested.emit()

    def show_message(self, title: str, message: str, icon=QSystemTrayIcon.MessageIcon.Information):
        """
        트레이 알림 표시

        Args:
            title: 알림 제목
            message: 알림 메시지
            icon: 알림 아이콘
        """
        if self.tray_icon and self.tray_icon.isVisible():
            self.tray_icon.showMessage(title, message, icon, 3000)  # 3초간 표시

    def set_paused(self, paused: bool):
        """
        일시 중지 상태 설정

        Args:
            paused: True면 일시 중지, False면 재개
        """
        self.is_paused = paused

        if self.action_pause:
            if paused:
                self.action_pause.setText("Resume")
            else:
                self.action_pause.setText("Pause")

    def hide(self):
        """트레이 아이콘 숨기기"""
        if self.tray_icon:
            self.tray_icon.hide()

    def show(self):
        """트레이 아이콘 표시"""
        if self.tray_icon:
            self.tray_icon.show()


# 테스트 코드
if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication, QMessageBox

    logging.basicConfig(level=logging.DEBUG)

    print("\n=== Testing TrayManager ===\n")

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 트레이 앱

    tray_manager = TrayManager()

    # Signals 연결
    def on_settings_requested():
        print("\n[Settings Requested]")
        QMessageBox.information(None, "Settings", "Settings window would open here")

    def on_pause_toggled(paused):
        print(f"\n[Pause Toggled]")
        print(f"  Status: {'Paused' if paused else 'Resumed'}")
        tray_manager.show_message(
            "Quill",
            f"Application {'paused' if paused else 'resumed'}"
        )

    def on_quit_requested():
        print(f"\n[Quit Requested]")
        reply = QMessageBox.question(
            None,
            "Quit Quill",
            "Are you sure you want to quit?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            print("[OK] Quitting...")
            app.quit()

    tray_manager.settings_requested.connect(on_settings_requested)
    tray_manager.pause_toggled.connect(on_pause_toggled)
    tray_manager.quit_requested.connect(on_quit_requested)

    # 트레이 아이콘 생성
    tray_manager.create_tray_icon()

    # 시작 알림
    tray_manager.show_message(
        "Quill Started",
        "Right-click the tray icon for options"
    )

    print("Tray icon created!")
    print("Right-click the tray icon to test the menu")
    print("Select 'Quit' from the menu to exit\n")

    sys.exit(app.exec())
