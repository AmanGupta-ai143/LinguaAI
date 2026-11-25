"""Password hashing and input validation for the lightweight account system.

Passwords are never stored: only a salted PBKDF2-HMAC-SHA256 hash is kept.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import secrets

ITERATIONS = 200_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{3,30}$")
MIN_PASSWORD_LENGTH = 6
MAX_PASSWORD_LENGTH = 128


def validate_username(username: str) -> str:
    username = (username or "").strip()
    if not USERNAME_RE.match(username):
        raise ValueError("Username must be 3-30 characters: letters, numbers, dot, dash or underscore.")
    if username.lower().startswith("guest-"):
        raise ValueError("Usernames starting with 'guest-' are reserved.")
    return username


def validate_password(password: str) -> str:
    password = password or ""
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(password) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at most {MAX_PASSWORD_LENGTH} characters.")
    return password


def hash_password(password: str, salt_hex: str | None = None) -> tuple[str, str]:
    """Return ``(hash_hex, salt_hex)``; a fresh random salt is generated when none is given."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, ITERATIONS)
    return digest.hex(), salt.hex()


def verify_password(password: str, hash_hex: str, salt_hex: str) -> bool:
    try:
        candidate, _ = hash_password(password, salt_hex)
    except ValueError:
        return False
    return hmac.compare_digest(candidate, hash_hex)
