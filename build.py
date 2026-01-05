"""
Quill 빌드 스크립트

PyInstaller를 사용하여 단일 실행 파일(.exe)을 생성합니다.

사용법:
    python build.py
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path


def clean_build_files():
    """이전 빌드 파일 정리"""
    print("Cleaning previous build files...")

    dirs_to_remove = ['build', 'dist']
    files_to_remove = ['Quill.spec']

    for dir_name in dirs_to_remove:
        if os.path.exists(dir_name):
            shutil.rmtree(dir_name)
            print(f"  Removed {dir_name}/")

    for file_name in files_to_remove:
        if os.path.exists(file_name):
            os.remove(file_name)
            print(f"  Removed {file_name}")


def check_requirements():
    """필수 패키지 확인"""
    print("\nChecking requirements...")

    try:
        import PyInstaller
        print("  PyInstaller: OK")
    except ImportError:
        print("  PyInstaller: NOT FOUND")
        print("\nInstalling PyInstaller...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])
        print("  PyInstaller installed successfully!")


def build_exe():
    """PyInstaller로 실행 파일 빌드"""
    print("\nBuilding Quill.exe...")

    # PyInstaller 명령어 구성
    cmd = [
        "pyinstaller",
        "--onedir",                       # 폴더 형태 (PySide6에 최적)
        "--windowed",                     # 콘솔 창 숨김
        "--name=Quill",                   # 실행 파일 이름
        "--clean",                        # 빌드 전 캐시 정리

        # 아이콘 (있으면)
        # "--icon=resources/icon.ico",

        # 데이터 파일 포함
        "--add-data=resources/default_prompts.json;resources",

        # PySide6 완전 포함 (필수!)
        "--collect-submodules=PySide6.QtCore",
        "--collect-submodules=PySide6.QtGui",
        "--collect-submodules=PySide6.QtWidgets",
        "--hidden-import=PySide6",

        # 불필요한 모듈 제외 (빌드 크기 최적화)
        "--exclude-module=matplotlib",
        "--exclude-module=numpy",
        "--exclude-module=pandas",
        "--exclude-module=scipy",
        "--exclude-module=PIL",
        "--exclude-module=PyQt5",
        "--exclude-module=tkinter",

        "main.py"
    ]

    # 빌드 실행
    print("\nRunning PyInstaller...")
    print(" ".join(cmd))
    print()

    result = subprocess.run(cmd)

    if result.returncode == 0:
        print("\n" + "="*50)
        print("Build completed successfully!")
        print("="*50)

        dist_folder = Path("dist") / "Quill"
        exe_path = dist_folder / "Quill.exe"
        if exe_path.exists():
            # 폴더 전체 크기 계산
            total_size = sum(f.stat().st_size for f in dist_folder.rglob('*') if f.is_file())
            size_mb = total_size / (1024 * 1024)
            print(f"\nApplication folder: {dist_folder}")
            print(f"Total size: {size_mb:.2f} MB")

            # 사용 안내
            print("\n" + "-"*50)
            print("How to use:")
            print("  1. Copy the entire 'dist/Quill' folder to your desired location")
            print("  2. Run Quill.exe inside the folder")
            print("  3. Configure API settings on first run")
            print("  4. Press Ctrl+Space to activate!")
            print("-"*50)

        return True
    else:
        print("\n" + "="*50)
        print("Build FAILED!")
        print("="*50)
        return False


def main():
    """메인 함수"""
    print("="*50)
    print("Quill Build Script")
    print("="*50)

    # 현재 디렉토리가 Quill 루트인지 확인
    if not Path("main.py").exists():
        print("\nError: main.py not found!")
        print("Please run this script from the Quill root directory.")
        sys.exit(1)

    # 1. 이전 빌드 파일 정리
    clean_build_files()

    # 2. 필수 패키지 확인
    check_requirements()

    # 3. 빌드
    success = build_exe()

    if success:
        print("\nBuild completed successfully!")
        sys.exit(0)
    else:
        print("\nBuild failed. Please check the error messages above.")
        sys.exit(1)


if __name__ == "__main__":
    main()
