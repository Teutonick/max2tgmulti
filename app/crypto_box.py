from __future__ import annotations

import base64
import hashlib
import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

_ENC_PREFIX = "enc:v1:"


class SecretBox:
    def __init__(self, master_key: str):
        if not master_key or not master_key.strip():
            raise ValueError("ENCRYPTION_KEY is empty")
        key = hashlib.sha256(master_key.encode("utf-8")).digest()
        self._aead = AESGCM(key)

    @staticmethod
    def is_encrypted(value: str) -> bool:
        return isinstance(value, str) and value.startswith(_ENC_PREFIX)

    def encrypt(self, plaintext: str) -> str:
        nonce = os.urandom(12)
        data = plaintext.encode("utf-8")
        ciphertext = self._aead.encrypt(nonce, data, associated_data=None)
        payload = base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")
        return f"{_ENC_PREFIX}{payload}"

    def decrypt(self, value: str) -> str:
        if not self.is_encrypted(value):
            return value
        payload_b64 = value[len(_ENC_PREFIX):]
        raw = base64.urlsafe_b64decode(payload_b64.encode("ascii"))
        nonce = raw[:12]
        ciphertext = raw[12:]
        plaintext = self._aead.decrypt(nonce, ciphertext, associated_data=None)
        return plaintext.decode("utf-8")
