"""
Quill - AI Writing Assistant

Windows 전용 백그라운드 AI 작문 보조 도구입니다.

사용법:
    python main.py

기능:
    - 전역 단축키 (기본: Ctrl+Space)로 활성화
    - 선택된 텍스트를 AI로 처리
    - ChatML 형식 프롬프트 지원
    - Windows DPAPI 암호화로 API 키 보호
    - 시스템 트레이에서 관리
"""

import sys
import logging
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox

# 참고: Qt 6 (PySide6)는 고DPI 스케일링이 기본 활성화됨

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.application import QuillApp
from core.single_instance import SingleInstanceLock
from core.diagnostics import setup_diagnostics, report_unhandled, record_exception, record


def setup_logging():
    """로깅 설정"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,  # 프로덕션: INFO, 개발: DEBUG
        format=log_format,
        handlers=[logging.StreamHandler(sys.stdout) if sys.stdout is not None else logging.NullHandler()],
    )


def acquire_instance_lock(lock):
    try:
        if lock.acquire():
            return True
    except OSError as exc:
        logging.getLogger(__name__).error("Could not access the Quill data folder: %s", exc)
        app = QApplication(sys.argv)
        QMessageBox.critical(
            None, "Quill Could Not Start",
            "Quill could not access its data folder. Move Quill to a folder you can write to, then try again."
        )
        return False

    app = QApplication(sys.argv)
    QMessageBox.warning(None, "Quill Already Running",
                        "Another instance of Quill is already running. Please check the system tray.")
    return False


def main():
    """메인 진입점"""
    # 로깅 설정
    setup_logging()

    logger = logging.getLogger(__name__)

    lock = None
    try:
        lock = SingleInstanceLock()
        # 단일 인스턴스 체크
        if not acquire_instance_lock(lock):
            sys.exit(1)

        setup_diagnostics()
        sys.excepthook = report_unhandled
        logger.info("="* 50)
        logger.info("Quill - AI Writing Assistant")
        logger.info("="* 50)

        # 애플리케이션 실행
        app = QuillApp(sys.argv)
        exit_code = app.exec()
        record('session.finished', exit_code=exit_code)

        # Lock 해제
        sys.exit(exit_code)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user, exiting...")
        sys.exit(0)

    except Exception as e:
        record_exception('session.failed', e.__traceback__)
        logger.error(f"Fatal error: {e}", exc_info=True)
        app = QApplication.instance() or QApplication(sys.argv)
        QMessageBox.critical(None, "Quill Could Not Start",
                             "Check that you extracted the whole Quill folder and can write to it. "
                             "See Quill's local events log for details.")
        sys.exit(1)
    finally:
        if lock is not None:
            lock.release()


if __name__ == "__main__":
    main()
