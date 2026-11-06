import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from core.single_instance import SingleInstanceLock


class SingleInstanceTests(unittest.TestCase):
    def test_cross_process_lock_survives_contention_and_can_be_reacquired(self):
        with tempfile.TemporaryDirectory() as folder:
            lock = SingleInstanceLock()
            lock.lock_file_path = Path(folder) / 'quill.lock'
            self.assertTrue(lock.acquire())
            self.assertTrue(lock.acquire())
            code = (
                'import sys; from pathlib import Path; '
                'from core.single_instance import SingleInstanceLock; '
                'lock = SingleInstanceLock(); lock.lock_file_path = Path(sys.argv[1]); '
                'acquired = lock.acquire(); lock.release(); sys.exit(0 if acquired else 2)'
            )
            try:
                result = subprocess.run([sys.executable, '-c', code, str(lock.lock_file_path)],
                                        capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 2, result.stderr)
            finally:
                lock.release()
            self.assertTrue(lock.lock_file_path.exists())
            result = subprocess.run([sys.executable, '-c', code, str(lock.lock_file_path)],
                                    capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(lock.acquire())
            lock.release()
            lock.release()


if __name__ == '__main__':
    unittest.main()
