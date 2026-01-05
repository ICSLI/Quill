"""
Windows DPAPI 기반 암호화 관리자

API 키를 Windows 사용자 계정에 바인딩하여 안전하게 저장합니다.
WritingTools의 XOR 난독화보다 훨씬 안전한 방식입니다.
"""

import base64
import ctypes
from ctypes import wintypes
import logging


logger = logging.getLogger(__name__)


class CryptoManager:
    """Windows DPAPI를 사용한 암호화 관리자"""

    def __init__(self):
        """CryptoManager 초기화"""
        try:
            self.crypt32 = ctypes.windll.crypt32
            self.kernel32 = ctypes.windll.kernel32
            logger.debug("CryptoManager initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize CryptoManager: {e}")
            raise RuntimeError("Windows DPAPI not available") from e

    def encrypt(self, plaintext: str) -> str:
        """
        문자열을 암호화하여 Base64 문자열로 반환

        Args:
            plaintext: 암호화할 평문 문자열

        Returns:
            Base64로 인코딩된 암호화된 문자열

        Raises:
            RuntimeError: 암호화 실패 시
        """
        if not plaintext:
            return ""

        try:
            # UTF-8로 인코딩
            plaintext_bytes = plaintext.encode('utf-8')

            # DATA_BLOB 구조체 정의
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ('cbData', wintypes.DWORD),
                    ('pbData', ctypes.POINTER(ctypes.c_char))
                ]

            # 입력 데이터 블롭 생성
            blob_in = DATA_BLOB()
            blob_in.cbData = len(plaintext_bytes)
            blob_in.pbData = ctypes.cast(
                ctypes.create_string_buffer(plaintext_bytes, len(plaintext_bytes)),
                ctypes.POINTER(ctypes.c_char)
            )

            # 출력 데이터 블롭
            blob_out = DATA_BLOB()

            # CryptProtectData 호출
            success = self.crypt32.CryptProtectData(
                ctypes.byref(blob_in),      # pDataIn
                None,                        # szDataDescr
                None,                        # pOptionalEntropy
                None,                        # pvReserved
                None,                        # pPromptStruct
                0,                           # dwFlags
                ctypes.byref(blob_out)       # pDataOut
            )

            if not success:
                error_code = self.kernel32.GetLastError()
                raise RuntimeError(f"CryptProtectData failed with error code {error_code}")

            # 암호화된 데이터 추출
            encrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)

            # 메모리 해제
            self.kernel32.LocalFree(blob_out.pbData)

            # Base64로 인코딩
            encoded = base64.b64encode(encrypted_bytes).decode('ascii')
            logger.debug(f"Successfully encrypted data (length: {len(plaintext)})")
            return encoded

        except Exception as e:
            logger.error(f"Encryption failed: {e}")
            raise RuntimeError(f"Encryption failed: {e}") from e

    def decrypt(self, ciphertext: str) -> str:
        """
        Base64 암호화 문자열을 복호화

        Args:
            ciphertext: Base64로 인코딩된 암호화 문자열

        Returns:
            복호화된 평문 문자열

        Raises:
            RuntimeError: 복호화 실패 시
        """
        if not ciphertext:
            return ""

        try:
            # Base64 디코딩
            encrypted_bytes = base64.b64decode(ciphertext)

            # DATA_BLOB 구조체 정의
            class DATA_BLOB(ctypes.Structure):
                _fields_ = [
                    ('cbData', wintypes.DWORD),
                    ('pbData', ctypes.POINTER(ctypes.c_char))
                ]

            # 입력 데이터 블롭 생성
            blob_in = DATA_BLOB()
            blob_in.cbData = len(encrypted_bytes)
            blob_in.pbData = ctypes.cast(
                ctypes.create_string_buffer(encrypted_bytes, len(encrypted_bytes)),
                ctypes.POINTER(ctypes.c_char)
            )

            # 출력 데이터 블롭
            blob_out = DATA_BLOB()

            # CryptUnprotectData 호출
            success = self.crypt32.CryptUnprotectData(
                ctypes.byref(blob_in),      # pDataIn
                None,                        # ppszDataDescr
                None,                        # pOptionalEntropy
                None,                        # pvReserved
                None,                        # pPromptStruct
                0,                           # dwFlags
                ctypes.byref(blob_out)       # pDataOut
            )

            if not success:
                error_code = self.kernel32.GetLastError()
                raise RuntimeError(f"CryptUnprotectData failed with error code {error_code}")

            # 복호화된 데이터 추출
            decrypted_bytes = ctypes.string_at(blob_out.pbData, blob_out.cbData)

            # 메모리 해제
            self.kernel32.LocalFree(blob_out.pbData)

            # UTF-8로 디코딩
            plaintext = decrypted_bytes.decode('utf-8')
            logger.debug(f"Successfully decrypted data (length: {len(plaintext)})")
            return plaintext

        except Exception as e:
            logger.error(f"Decryption failed: {e}")
            raise RuntimeError(f"Decryption failed: {e}") from e


# 간단한 테스트 코드
if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)

    crypto = CryptoManager()

    # 테스트
    test_data = "sk-test-1234567890abcdefghijklmnopqrstuvwxyz"
    print(f"Original: {test_data}")

    # 암호화
    encrypted = crypto.encrypt(test_data)
    print(f"Encrypted: {encrypted[:50]}...")

    # 복호화
    decrypted = crypto.decrypt(encrypted)
    print(f"Decrypted: {decrypted}")

    # 검증
    assert test_data == decrypted, "Encryption/Decryption test failed!"
    print("\n✅ Encryption test passed!")
