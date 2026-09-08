"""bcrypt password hashing and verification primitives."""

import bcrypt

MAX_BCRYPT_PASSWORD_BYTES = 72


def _password_bytes(password: str) -> bytes:
    encoded = password.encode("utf-8")
    if not encoded:
        raise ValueError("Password cannot be empty")
    if len(encoded) > MAX_BCRYPT_PASSWORD_BYTES:
        raise ValueError("Password exceeds bcrypt's 72-byte limit")
    return encoded


def hash_password(password: str) -> str:
    """Hash a one-way password value using bcrypt's current safe defaults."""

    return bcrypt.hashpw(_password_bytes(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a candidate without exposing parsing or length failures."""

    try:
        return bcrypt.checkpw(
            _password_bytes(password),
            password_hash.encode("utf-8"),
        )
    except (TypeError, ValueError):
        return False
