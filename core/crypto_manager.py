"""Windows account-bound API key encryption using DPAPI."""

import base64
import ctypes
from ctypes import wintypes


class DATA_BLOB(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class CryptoManager:
    """Protect secrets with the current user's Windows credentials."""

    def __init__(self):
        try:
            self.crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
            self.kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
            blob_pointer = ctypes.POINTER(DATA_BLOB)
            common_tail = [blob_pointer, ctypes.c_void_p, ctypes.c_void_p,
                           wintypes.DWORD, blob_pointer]
            self.crypt32.CryptProtectData.argtypes = [
                blob_pointer, wintypes.LPCWSTR, *common_tail,
            ]
            self.crypt32.CryptUnprotectData.argtypes = [
                blob_pointer, ctypes.POINTER(wintypes.LPWSTR), *common_tail,
            ]
            self.crypt32.CryptProtectData.restype = wintypes.BOOL
            self.crypt32.CryptUnprotectData.restype = wintypes.BOOL
            # Explicit pointer-sized signature is required on 64-bit Windows.
            self.kernel32.LocalFree.argtypes = [ctypes.c_void_p]
            self.kernel32.LocalFree.restype = ctypes.c_void_p
        except (AttributeError, OSError) as exc:
            raise RuntimeError("Windows DPAPI not available") from exc

    def _transform(self, data: bytes, operation) -> bytes:
        buffer = ctypes.create_string_buffer(data)
        blob_in = DATA_BLOB(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)))
        blob_out = DATA_BLOB()
        try:
            # CRYPTPROTECT_UI_FORBIDDEN: never display an OS prompt in a worker.
            if not operation(ctypes.byref(blob_in), None, None, None, None, 1,
                             ctypes.byref(blob_out)):
                raise ctypes.WinError(ctypes.get_last_error())
            return ctypes.string_at(blob_out.pbData, blob_out.cbData)
        finally:
            if blob_out.pbData:
                self.kernel32.LocalFree(ctypes.cast(blob_out.pbData, ctypes.c_void_p))

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        try:
            protected = self._transform(plaintext.encode("utf-8"), self.crypt32.CryptProtectData)
            return base64.b64encode(protected).decode("ascii")
        except Exception as exc:
            raise RuntimeError("API key encryption failed") from exc

    def decrypt(self, ciphertext: str) -> str:
        if not ciphertext:
            return ""
        try:
            protected = base64.b64decode(ciphertext, validate=True)
            return self._transform(protected, self.crypt32.CryptUnprotectData).decode("utf-8")
        except Exception as exc:
            raise RuntimeError("API key decryption failed") from exc
