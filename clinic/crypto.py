"""Symmetric encryption utilities (AES-GCM).

This module provides a small, focused wrapper around `cryptography`'s `AESGCM`.

Core ideas implemented here:
- Key management: a single application master key is provided via
    `AES_MASTER_KEY_B64` (base64-encoded bytes).
- Authenticated encryption: AES-GCM provides both confidentiality and integrity.
- Random nonce per encryption: required for GCM security; we generate 12 bytes.
- Versioned payload format: stored as a string so it can live in a normal
    Django `TextField`.

Payload format (v1):
    enc:v1:<nonce_b64>:<ciphertext_b64>

Notes:
- Never reuse the same (key, nonce) pair.
- Keep the master key secret; rotating keys requires a migration strategy.
"""

import base64
import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from django.conf import settings


class CryptoConfigurationError(RuntimeError):
    """Raised when crypto configuration (e.g., master key) is missing/invalid."""

    pass


@dataclass(frozen=True)
class EncryptedPayload:
    """In-memory representation of an encrypted payload string."""

    version: str
    nonce_b64: str
    ciphertext_b64: str

    def serialize(self) -> str:
        """Serialize to the DB-friendly `enc:<version>:<nonce>:<ciphertext>` format."""
        return f"enc:{self.version}:{self.nonce_b64}:{self.ciphertext_b64}"


_PREFIX = "enc:v1:"


def _get_master_key() -> bytes:
    """Load and validate the master key.

    The key is expected to be base64-encoded and provided via either:
    - Django settings: `settings.AES_MASTER_KEY_B64`
    - Environment: `AES_MASTER_KEY_B64`
    """

    key_b64 = getattr(settings, "AES_MASTER_KEY_B64", "") or os.environ.get("AES_MASTER_KEY_B64", "")
    if not key_b64:
        raise CryptoConfigurationError(
            "AES_MASTER_KEY_B64 is not configured. Set it in .env (base64-encoded 32-byte key)."
        )

    try:
        key = base64.b64decode(key_b64)
    except Exception as exc:  # noqa: BLE001
        raise CryptoConfigurationError("AES_MASTER_KEY_B64 is not valid base64") from exc

    if len(key) not in (16, 24, 32):
        raise CryptoConfigurationError("AES_MASTER_KEY_B64 must decode to 16/24/32 bytes")

    return key


def encrypt_str(plaintext: str, *, aad: bytes = b"ua-clinic") -> str:
    """Encrypt a plaintext string into a versioned, self-describing payload.

    Args:
        plaintext: The UTF-8 string to encrypt.
        aad: "Additional authenticated data". This is NOT secret, but it is
            covered by the authentication tag; decryption will fail if AAD
            differs. We use it as an application/domain separator.

    Returns:
        A string starting with `enc:v1:` that can be stored in the database.
    """

    if plaintext is None:
        return None  # type: ignore[return-value]
    if not isinstance(plaintext, str):
        raise TypeError("encrypt_str expects a str")
    if plaintext.startswith(_PREFIX):
        # Idempotency guard: don't double-encrypt if the value is already in
        # the expected encrypted payload format.
        return plaintext

    key = _get_master_key()
    aesgcm = AESGCM(key)
    # GCM nonce should be unique per encryption for a given key.
    # 96-bit (12-byte) nonces are the recommended size for AES-GCM.
    nonce = os.urandom(12)
    ciphertext = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), aad)

    payload = EncryptedPayload(
        version="v1",
        nonce_b64=base64.b64encode(nonce).decode("ascii"),
        ciphertext_b64=base64.b64encode(ciphertext).decode("ascii"),
    )
    return payload.serialize()


def decrypt_str(value: str, *, aad: bytes = b"ua-clinic") -> str:
    """Decrypt a payload produced by :func:`encrypt_str`.

    If the value doesn't look encrypted (no `enc:v1:` prefix), we treat it as
    plaintext to support legacy/unencrypted rows.

    Raises:
        ValueError: If the payload format/version is invalid.
        cryptography.exceptions.InvalidTag: If authentication fails (wrong key,
            wrong AAD, corrupted ciphertext, etc.).
    """

    if value is None:
        return None  # type: ignore[return-value]
    if not isinstance(value, str):
        raise TypeError("decrypt_str expects a str")

    if not value.startswith(_PREFIX):
        # Assume plaintext (e.g., legacy/unencrypted data)
        return value

    # enc:v1:<nonce_b64>:<ciphertext_b64>
    parts = value.split(":", 3)
    if len(parts) != 4:
        raise ValueError("Invalid encrypted payload format")

    _enc, version, nonce_b64, ciphertext_b64 = parts
    if version != "v1":
        raise ValueError(f"Unsupported encryption version: {version}")

    # Decode the stored nonce/ciphertext back into raw bytes.
    nonce = base64.b64decode(nonce_b64)
    ciphertext = base64.b64decode(ciphertext_b64)

    key = _get_master_key()
    aesgcm = AESGCM(key)
    plaintext = aesgcm.decrypt(nonce, ciphertext, aad)
    return plaintext.decode("utf-8")
