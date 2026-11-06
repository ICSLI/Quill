"""Build the portable Windows application with the current Python environment."""

import importlib.util
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def check_requirements():
    if importlib.util.find_spec('PyInstaller') is None:
        raise RuntimeError('PyInstaller is missing. Run: python -m pip install pyinstaller')


def build_exe():
    cmd = [
        sys.executable, '-m', 'PyInstaller',
        '--onedir', '--windowed', '--name=Quill', '--clean', '--noconfirm',
        f'--icon={PROJECT_ROOT / "resources" / "icon.ico"}',
        f'--add-data={PROJECT_ROOT / "resources" / "default_prompts.json"};resources',
        f'--add-data={PROJECT_ROOT / "resources" / "icon.ico"};resources',
        f'--add-data={PROJECT_ROOT / "resources" / "icon_alpha.ico"};resources',
        '--exclude-module=matplotlib', '--exclude-module=numpy',
        '--exclude-module=pandas', '--exclude-module=scipy',
        '--exclude-module=PIL', '--exclude-module=PyQt5', '--exclude-module=tkinter',
        str(PROJECT_ROOT / 'main.py'),
    ]
    # Qt hooks collect the imported QtCore/QtGui/QtWidgets dependencies.
    # Avoid collecting unrelated Qt modules or installing packages during a build.
    result = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if result.returncode:
        return False
    exe_path = PROJECT_ROOT / 'dist' / 'Quill' / 'Quill.exe'
    if not exe_path.is_file():
        return False
    print(f'Build complete: {exe_path}')
    print('Distribute the entire dist/Quill folder, including _internal.')
    return True


def main():
    try:
        check_requirements()
        return 0 if build_exe() else 1
    except (OSError, RuntimeError) as exc:
        print(f'Build failed: {exc}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
