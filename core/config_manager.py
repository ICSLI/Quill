"""
설정 파일 관리자

JSON 설정 파일의 로드/저장을 담당하며, CryptoManager를 통해 API 키를 안전하게 암호화합니다.
"""

import json
import os
import logging
from pathlib import Path
from typing import Dict, Any, Optional

from core.crypto_manager import CryptoManager


logger = logging.getLogger(__name__)


class ConfigManager:
    """설정 파일 관리자"""

    DEFAULT_CONFIG = {
        "version": "1.0.0",
        "api": {
            "base_url": "https://api.openai.com/v1",
            "api_key_encrypted": "",
            "model": "gpt-4",
            "additional_params": {}
        },
        "hotkey": {
            "key": "<ctrl>+<space>",
            "enabled": True
        },
        "ui": {
            "theme": "dark"
        }
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        ConfigManager 초기화

        Args:
            config_path: 설정 파일 경로 (기본값: data/config.json)
        """
        if config_path is None:
            # 프로젝트 루트 기준 data/config.json
            project_root = Path(__file__).parent.parent
            config_path = project_root / "data" / "config.json"

        self.config_path = Path(config_path)
        self.crypto = CryptoManager()
        self._config: Dict[str, Any] = {}

        logger.debug(f"ConfigManager initialized with path: {self.config_path}")

    def is_configured(self) -> bool:
        """
        설정 파일이 존재하고 유효한지 확인

        Returns:
            설정 파일이 존재하고 필수 설정(base_url, model)이 있으면 True
            (API 키는 선택사항이므로 검사하지 않음)
        """
        if not self.config_path.exists():
            logger.debug("Config file does not exist")
            return False

        try:
            config = self.load()
            api_config = config.get("api", {})
            base_url = api_config.get("base_url", "")
            model = api_config.get("model", "")
            is_valid = bool(base_url and model)
            logger.debug(f"Config file exists, configured: {is_valid} (base_url={bool(base_url)}, model={bool(model)})")
            return is_valid
        except Exception as e:
            logger.error(f"Error checking configuration: {e}")
            return False

    def load(self) -> Dict[str, Any]:
        """
        설정 파일 로드

        Returns:
            설정 딕셔너리

        Raises:
            FileNotFoundError: 설정 파일이 존재하지 않는 경우
            json.JSONDecodeError: JSON 파싱 실패 시
        """
        if not self.config_path.exists():
            logger.warning(f"Config file not found: {self.config_path}")
            raise FileNotFoundError(f"Config file not found: {self.config_path}")

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self._config = json.load(f)
            logger.info(f"Configuration loaded successfully from {self.config_path}")
            return self._config
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in config file: {e}")
            raise
        except Exception as e:
            logger.error(f"Error loading config: {e}")
            raise

    def save(self, config: Optional[Dict[str, Any]] = None) -> None:
        """
        설정 파일 저장

        Args:
            config: 저장할 설정 딕셔너리 (None이면 현재 설정 사용)

        Raises:
            OSError: 파일 쓰기 실패 시
        """
        if config is not None:
            self._config = config

        # data 디렉토리가 없으면 생성
        self.config_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            logger.info(f"Configuration saved to {self.config_path}")
        except Exception as e:
            logger.error(f"Error saving config: {e}")
            raise

    def get(self, key: str, default: Any = None) -> Any:
        """
        설정 값 가져오기 (점 표기법 지원)

        Args:
            key: 설정 키 (예: "api.base_url")
            default: 기본값

        Returns:
            설정 값

        Example:
            >>> config.get("api.base_url")
            "https://api.openai.com/v1"
        """
        keys = key.split('.')
        value = self._config

        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                logger.debug(f"Key not found: {key}, returning default: {default}")
                return default

        return value

    def set(self, key: str, value: Any) -> None:
        """
        설정 값 설정 (점 표기법 지원)

        Args:
            key: 설정 키 (예: "api.base_url")
            value: 설정 값

        Example:
            >>> config.set("api.model", "gpt-4-turbo")
        """
        keys = key.split('.')
        target = self._config

        for k in keys[:-1]:
            if k not in target:
                target[k] = {}
            target = target[k]

        target[keys[-1]] = value
        logger.debug(f"Set config: {key} = {value}")

    def get_api_key(self) -> str:
        """
        API 키 복호화하여 가져오기

        Returns:
            복호화된 API 키

        Raises:
            RuntimeError: 복호화 실패 시
        """
        encrypted_key = self.get("api.api_key_encrypted", "")
        if not encrypted_key:
            logger.warning("No API key found in config")
            return ""

        try:
            decrypted = self.crypto.decrypt(encrypted_key)
            logger.debug("API key decrypted successfully")
            return decrypted
        except Exception as e:
            logger.error(f"Failed to decrypt API key: {e}")
            raise RuntimeError("Failed to decrypt API key") from e

    def set_api_key(self, api_key: str) -> None:
        """
        API 키 암호화하여 저장

        Args:
            api_key: 평문 API 키

        Raises:
            RuntimeError: 암호화 실패 시
        """
        try:
            encrypted = self.crypto.encrypt(api_key)
            self.set("api.api_key_encrypted", encrypted)
            logger.debug("API key encrypted and set successfully")
        except Exception as e:
            logger.error(f"Failed to encrypt API key: {e}")
            raise RuntimeError("Failed to encrypt API key") from e

    def create_default_config(self) -> None:
        """
        기본 설정 파일 생성
        """
        logger.info("Creating default config")
        self._config = self.DEFAULT_CONFIG.copy()
        self.save()

    def get_all(self) -> Dict[str, Any]:
        """
        전체 설정 가져오기

        Returns:
            전체 설정 딕셔너리
        """
        return self._config.copy()


# 간단한 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    # 테스트용 임시 설정 파일
    test_config_path = Path(__file__).parent.parent / "data" / "test_config.json"

    # ConfigManager 생성
    config = ConfigManager(test_config_path)

    print("\n=== Testing ConfigManager ===\n")

    # 1. 기본 설정 생성
    print("1. Creating default config...")
    config.create_default_config()
    print(f"   Config file created at: {test_config_path}")

    # 2. API 키 설정
    print("\n2. Setting API key...")
    test_api_key = "sk-test-my-secret-api-key-1234567890"
    config.set_api_key(test_api_key)
    config.save()
    print(f"   API key set: {test_api_key[:15]}...")

    # 3. 설정 로드
    print("\n3. Loading config...")
    loaded_config = config.load()
    print(f"   Config version: {config.get('version')}")
    print(f"   Base URL: {config.get('api.base_url')}")
    print(f"   Model: {config.get('api.model')}")
    print(f"   Hotkey: {config.get('hotkey.key')}")

    # 4. API 키 복호화
    print("\n4. Decrypting API key...")
    decrypted_key = config.get_api_key()
    print(f"   Decrypted: {decrypted_key[:15]}...")

    # 5. 검증
    assert test_api_key == decrypted_key, "API key encryption/decryption test failed!"
    print("\n[OK] All tests passed!")

    # 정리
    print(f"\nTest config file saved at: {test_config_path}")
