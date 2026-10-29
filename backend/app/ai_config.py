from __future__ import annotations

from cryptography.fernet import Fernet, InvalidToken


class AIConfigStorageError(RuntimeError):
    """Raised when an AI configuration cannot be encrypted or decrypted."""


class AIConfigCipher:
    """Encrypts provider API keys before they are stored with a user record."""

    def __init__(self, encryption_key: str) -> None:
        self._fernet = None
        if encryption_key.strip():
            try:
                self._fernet = Fernet(encryption_key.strip().encode("utf-8"))
            except (ValueError, TypeError) as error:
                raise AIConfigStorageError("AI_CONFIG_ENCRYPTION_KEY 格式无效") from error

    @property
    def configured(self) -> bool:
        return self._fernet is not None

    def encrypt(self, value: str) -> str:
        if self._fernet is None:
            raise AIConfigStorageError("服务端尚未配置 AI_CONFIG_ENCRYPTION_KEY")
        return self._fernet.encrypt(value.encode("utf-8")).decode("utf-8")

    def decrypt(self, value: str) -> str:
        if self._fernet is None:
            raise AIConfigStorageError("服务端尚未配置 AI_CONFIG_ENCRYPTION_KEY")
        try:
            return self._fernet.decrypt(value.encode("utf-8")).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as error:
            raise AIConfigStorageError("AI API Key 无法解密，请检查服务端加密配置") from error
