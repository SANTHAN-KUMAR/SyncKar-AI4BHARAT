"""
RSA signing for audit rows — AGENTS.md §11, BSA 2023 compliance.
Every audit row is signed with the middleware's private key for tamper evidence.
"""

import base64
import os

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.backends import default_backend
import structlog

from synckar.config import settings

logger = structlog.get_logger()

_private_key = None
_public_key = None


def _load_private_key():
    """Load RSA private key from file or base64 env var."""
    global _private_key
    if _private_key:
        return _private_key

    # Try base64 env var first (for cloud deployment)
    if settings.signing.rsa_private_key_base64:
        key_bytes = base64.b64decode(settings.signing.rsa_private_key_base64)
        _private_key = serialization.load_pem_private_key(
            key_bytes, password=None, backend=default_backend()
        )
        return _private_key

    # Try file path
    key_path = settings.signing.rsa_private_key_path
    if key_path and os.path.exists(key_path):
        with open(key_path, "rb") as f:
            _private_key = serialization.load_pem_private_key(
                f.read(), password=None, backend=default_backend()
            )
        return _private_key

    raise RuntimeError(
        "RSA private key not found. Set RSA_PRIVATE_KEY_PATH or RSA_PRIVATE_KEY_BASE64."
    )


def _load_public_key():
    """Load RSA public key."""
    global _public_key
    if _public_key:
        return _public_key

    key_path = settings.signing.rsa_public_key_path
    if key_path and os.path.exists(key_path):
        with open(key_path, "rb") as f:
            _public_key = serialization.load_pem_public_key(
                f.read(), backend=default_backend()
            )
        return _public_key

    # Derive from private key
    _public_key = _load_private_key().public_key()
    return _public_key


def sign_audit_row(row_data: str) -> str:
    """
    Sign audit row data with RSA private key.
    Returns base64-encoded signature.
    """
    private_key = _load_private_key()
    signature = private_key.sign(
        row_data.encode("utf-8"),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return base64.b64encode(signature).decode("utf-8")


def verify_signature(row_data: str, signature_b64: str) -> bool:
    """
    Verify RSA signature on audit row data.
    Returns True if valid, False if tampered.
    """
    try:
        public_key = _load_public_key()
        signature = base64.b64decode(signature_b64)
        public_key.verify(
            signature,
            row_data.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return True
    except Exception:
        return False
