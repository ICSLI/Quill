# Quill 실행 파일 빌드 가이드

## 빠른 시작

```bash
# Quill 디렉토리에서
python build.py
```

빌드가 완료되면 `dist/Quill.exe` 파일이 생성됩니다.

## 상세 단계

### 1. PyInstaller 설치 (자동)

빌드 스크립트가 자동으로 PyInstaller를 설치합니다. 수동으로 설치하려면:

```bash
pip install pyinstaller
```

### 2. 빌드 실행

```bash
cd C:\Users\tim54\Documents\AI\Quill
python build.py
```

빌드 과정:
- 이전 빌드 파일 정리
- PyInstaller 확인 및 설치
- 실행 파일 생성 (약 2-5분 소요)

### 3. 빌드 결과

빌드가 성공하면 다음이 생성됩니다:

```
Quill/
├── build/         # 임시 빌드 파일 (삭제 가능)
├── dist/          # 최종 실행 파일
│   └── Quill.exe  # 이것이 배포할 파일입니다!
└── Quill.spec     # PyInstaller 설정 파일
```

### 4. 실행 파일 사용

1. `dist/Quill.exe`를 원하는 위치로 복사
2. 더블클릭으로 실행
3. 첫 실행 시 API 설정
4. 이후부터는 백그라운드에서 실행

## 빌드 옵션 설명

### 현재 설정

- **`--onefile`**: 단일 `.exe` 파일로 생성 (모든 의존성 포함)
- **`--windowed`**: 콘솔 창 없이 실행
- **`--name=Quill`**: 실행 파일 이름
- **`--clean`**: 빌드 전 캐시 정리

### 리소스 파일 포함

```python
"--add-data=resources/default_prompts.json;resources"
```

`default_prompts.json` 파일이 실행 파일에 포함됩니다.

### 불필요한 모듈 제외

빌드 크기를 줄이기 위해 사용하지 않는 모듈을 제외합니다:
- matplotlib, numpy, pandas (데이터 분석)
- PIL (이미지 처리)
- PySide6의 불필요한 모듈 (3D, Charts, WebEngine 등)

## 빌드 크기 최적화

### 예상 크기

- **전체 빌드**: 약 100-150 MB
- **최적화 후**: 약 80-120 MB

### 추가 최적화 방법

1. **UPX 압축** (선택적)
```bash
# UPX 다운로드: https://upx.github.io/
# build.py에 추가:
"--upx-dir=path/to/upx"
```

2. **단일 폴더 빌드** (더 빠른 시작)
```python
# --onefile 대신 --onedir 사용
"--onedir"
```

## 문제 해결

### 1. "PyInstaller not found"

```bash
pip install pyinstaller
```

### 2. 빌드 실패 - 모듈을 찾을 수 없음

모든 의존성이 설치되어 있는지 확인:
```bash
pip install -r requirements.txt
```

### 3. 실행 파일이 느리게 시작됨

`--onefile` 모드는 시작 시 압축 해제가 필요합니다.
더 빠른 시작을 원하면 `build.py`에서 `--onedir`로 변경하세요.

### 4. 바이러스 경고

PyInstaller로 만든 실행 파일은 때때로 오탐지될 수 있습니다.
이는 정상적인 현상이며, 다음을 시도해보세요:
- Windows Defender 예외 추가
- 디지털 서명 추가 (고급)

### 5. 리소스 파일이 누락됨

`--add-data` 옵션을 확인하세요:
```python
"--add-data=source;destination"  # Windows
"--add-data=source:destination"  # Linux/Mac
```

## 고급 빌드

### 커스텀 아이콘 추가

1. `.ico` 파일 준비 (256x256 권장)
2. `resources/icon.ico`에 저장
3. `build.py`에서 주석 제거:
```python
"--icon=resources/icon.ico"
```

### 버전 정보 추가 (Windows)

```bash
pyinstaller ... --version-file=version_info.txt
```

`version_info.txt`:
```
VSVersionInfo(
  ffi=FixedFileInfo(
    filevers=(1, 0, 0, 0),
    prodvers=(1, 0, 0, 0),
    ...
  ),
  ...
)
```

### 단일 폴더 빌드 (더 빠른 시작)

`build.py` 수정:
```python
"--onedir",  # --onefile 대신
```

결과:
```
dist/
└── Quill/
    ├── Quill.exe
    ├── _internal/  # 의존성 파일들
    └── ...
```

## 배포

### 최종 사용자에게 배포

1. **단일 파일 배포**
   - `dist/Quill.exe`만 배포
   - 사용자는 다운로드 후 바로 실행

2. **압축 배포**
   ```bash
   # dist/Quill.exe를 ZIP으로 압축
   zip Quill-v1.0.zip dist/Quill.exe
   ```

3. **설치 프로그램** (고급)
   - NSIS, Inno Setup 등 사용
   - 시작 프로그램 등록 자동화

### 자동 업데이트 (향후)

WritingTools의 `update_checker.py`를 참고하여 구현 가능:
- GitHub Releases API 사용
- 새 버전 확인 및 다운로드 안내

## 참고 자료

- [PyInstaller 공식 문서](https://pyinstaller.org/)
- [PyInstaller 옵션](https://pyinstaller.org/en/stable/usage.html)
- [WritingTools 빌드 스크립트](../WritingTools/Windows_and_Linux/pyinstaller-build-script.py)

## 빌드 체크리스트

- [ ] 모든 의존성 설치 확인
- [ ] `python main.py`로 정상 실행 확인
- [ ] `python build.py` 실행
- [ ] `dist/Quill.exe` 생성 확인
- [ ] 실행 파일 테스트 (깨끗한 환경에서)
- [ ] 첫 실행 온보딩 테스트
- [ ] API 호출 테스트
- [ ] 시스템 트레이 테스트

---

빌드가 완료되면 `dist/Quill.exe`를 USB나 클라우드로 공유하여 다른 PC에서도 사용할 수 있습니다!
