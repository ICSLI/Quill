"""
Single Instance Lock

다른 Quill 인스턴스가 이미 실행 중인지 확인합니다.
"""

import os
import sys
import logging
from pathlib import Path


logger = logging.getLogger(__name__)


class SingleInstanceLock:
    """단일 인스턴스 Lock 관리자"""

    def __init__(self, lock_file_name="quill.lock"):
        """
        SingleInstanceLock 초기화

        Args:
            lock_file_name: Lock 파일 이름
        """
        # Lock 파일 경로 (프로젝트 data 폴더)
        project_root = Path(__file__).parent.parent
        data_dir = project_root / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        self.lock_file_path = data_dir / lock_file_name
        self.lock_file = None

    def acquire(self) -> bool:
        """
        Lock 획득 시도

        Returns:
            True면 Lock 획득 성공 (첫 인스턴스), False면 이미 다른 인스턴스 실행 중
        """
        try:
            # Windows에서는 exclusive 모드로 파일 열기
            if sys.platform == "win32":
                import msvcrt

                # 파일 열기
                self.lock_file = open(self.lock_file_path, "w")

                # Exclusive lock 시도
                try:
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_NBLCK, 1)
                except IOError:
                    self.lock_file.close()
                    self.lock_file = None
                    logger.warning("Another instance of Quill is already running")
                    return False

            else:
                # Unix-like 시스템 (향후 확장용)
                import fcntl

                self.lock_file = open(self.lock_file_path, "w")

                try:
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                except IOError:
                    self.lock_file.close()
                    self.lock_file = None
                    logger.warning("Another instance of Quill is already running")
                    return False

            # PID 기록
            self.lock_file.write(str(os.getpid()))
            self.lock_file.flush()

            logger.info("Single instance lock acquired")
            return True

        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")
            return False

    def release(self):
        """Lock 해제"""
        if self.lock_file:
            try:
                if sys.platform == "win32":
                    import msvcrt
                    msvcrt.locking(self.lock_file.fileno(), msvcrt.LK_UNLCK, 1)

                else:
                    import fcntl
                    fcntl.flock(self.lock_file.fileno(), fcntl.LOCK_UN)

                self.lock_file.close()
                self.lock_file = None

                # Lock 파일 삭제
                if self.lock_file_path.exists():
                    self.lock_file_path.unlink()

                logger.info("Single instance lock released")

            except Exception as e:
                logger.error(f"Error releasing lock: {e}")

    def __enter__(self):
        """Context manager 진입"""
        if not self.acquire():
            raise RuntimeError("Another instance of Quill is already running")
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager 종료"""
        self.release()


# 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    print("\n=== Testing SingleInstanceLock ===\n")

    lock = SingleInstanceLock()

    if lock.acquire():
        print("[OK] Lock acquired successfully!")
        print(f"Lock file: {lock.lock_file_path}")
        print("\nTry running this script in another terminal to test.")
        print("Press Enter to release lock...")
        input()
        lock.release()
        print("[OK] Lock released")
    else:
        print("[ERROR] Another instance is already running!")
