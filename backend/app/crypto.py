"""Encrypt/decrypt IntegrationConnection config blobs.

Per docs/ARCHITECTURE.md, integration credentials are sensitive and must not
sit in plaintext. Each connection's config dict (tenant IDs, API keys,
secrets) is serialized to JSON and encrypted as one blob with Fernet
(symmetric, authenticated) under a single master key (SECRET_ENCRYPTION_KEY).
"""

import json

from cryptography.fernet import Fernet, InvalidToken

from app.config import settings


class EncryptionNotConfigured(Exception):
    pass


def _get_fernet() -> Fernet:
    if not settings.secret_encryption_key:
        raise EncryptionNotConfigured(
            "SECRET_ENCRYPTION_KEY is not set. Generate one with: "
            "python -c \"from cryptography.fernet import Fernet; "
            "print(Fernet.generate_key().decode())\" and add it to backend/.env."
        )
    return Fernet(settings.secret_encryption_key.encode())


def encrypt_config(config: dict) -> str:
    return _get_fernet().encrypt(json.dumps(config).encode()).decode()


def decrypt_config(ciphertext: str | None) -> dict:
    if not ciphertext:
        return {}
    try:
        return json.loads(_get_fernet().decrypt(ciphertext.encode()).decode())
    except InvalidToken as e:
        raise EncryptionNotConfigured(
            "Could not decrypt stored integration config — SECRET_ENCRYPTION_KEY "
            "may have changed since it was saved."
        ) from e
