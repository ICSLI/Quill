"""Keep one running instance per portable data directory."""

import errno
import sys
from pathlib import Path


class SingleInstanceLock:
    def __init__(self, lock_file_name="quill.lock"):
        self.lock_file_path = Path(__file__).parent.parent / "data" / lock_file_name
        self.lock_file = None

    def acquire(self) -> bool:
        """Return False on lock contention and raise on filesystem errors."""
        if self.lock_file is not None:
            return True

        self.lock_file_path.parent.mkdir(parents=True, exist_ok=True)
        stream = self.lock_file_path.open("a+b")
        try:
            if sys.platform == "win32":
                import msvcrt

                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if exc.errno in (errno.EACCES, errno.EAGAIN):
                return False
            raise
        else:
            self.lock_file = stream
            return True
        finally:
            if self.lock_file is None:
                stream.close()

    def release(self):
        # Closing the descriptor releases the OS lock. Keep the file in place so
        # other processes always open the same lock target.
        if self.lock_file is not None:
            stream, self.lock_file = self.lock_file, None
            stream.close()
