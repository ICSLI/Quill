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
from PySide6.QtWidgets import QMessageBox

# 참고: Qt 6 (PySide6)는 고DPI 스케일링이 기본 활성화됨

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.application import QuillApp
from core.single_instance import SingleInstanceLock


def setup_logging():
    """로깅 설정"""
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    logging.basicConfig(
        level=logging.INFO,  # 프로덕션: INFO, 개발: DEBUG
        format=log_format,
        handlers=[
            # 콘솔 출력
            logging.StreamHandler(sys.stdout),
            # 파일 출력 (선택적)
            # logging.FileHandler('quill.log', encoding='utf-8')
        ]
    )


def main():
    """메인 진입점"""
    # 로깅 설정
    setup_logging()

    logger = logging.getLogger(__name__)

    try:
        # 단일 인스턴스 체크
        lock = SingleInstanceLock()
        if not lock.acquire():
            logger.warning("Another instance of Quill is already running")
            # GUI 에러 메시지 표시
            from PySide6.QtWidgets import QApplication
            temp_app = QApplication(sys.argv)
            QMessageBox.warning(
                None,
                "Quill Already Running",
                "Another instance of Quill is already running.\n\nPlease check the system tray."
            )
            sys.exit(1)

        logger.info("="* 50)
        logger.info("Quill - AI Writing Assistant")
        logger.info("="* 50)

        # 애플리케이션 실행
        app = QuillApp(sys.argv)
        exit_code = app.exec()

        # Lock 해제
        lock.release()
        sys.exit(exit_code)

    except KeyboardInterrupt:
        logger.info("\nInterrupted by user, exiting...")
        sys.exit(0)

    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
