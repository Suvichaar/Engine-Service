"""Authentication helpers — JWT issuing, password verification, and the
`get_current_user` FastAPI dependency used by protected endpoints.

Admin credentials are read from environment variables so secrets never live
in `settings.toml`:

    ADMIN_EMAIL              admin login email
    ADMIN_PASSWORD_HASH      bcrypt hash of the password
                             (generate via `scripts/hash_password.py`)
    JWT_SECRET               secret used to sign access tokens
    JWT_ALGORITHM            (optional) default "HS256"
    JWT_EXPIRES_MINUTES      (optional) default 720 (12 hours)
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Optional

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel


logger = logging.getLogger(__name__)

# bcrypt accepts a max of 72 bytes; longer passwords are truncated explicitly.
_BCRYPT_MAX_BYTES = 72

_bearer_scheme = HTTPBearer(auto_error=False)


def _to_bcrypt_bytes(value: str) -> bytes:
    encoded = value.encode("utf-8")
    if len(encoded) > _BCRYPT_MAX_BYTES:
        encoded = encoded[:_BCRYPT_MAX_BYTES]
    return encoded


# ── Configuration ────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class AuthConfig:
    admin_email: str
    admin_password_hash: str
    jwt_secret: str
    jwt_algorithm: str
    jwt_expires_minutes: int

    @property
    def configured(self) -> bool:
        return bool(self.admin_email and self.admin_password_hash and self.jwt_secret)


@lru_cache(maxsize=1)
def get_auth_config() -> AuthConfig:
    return AuthConfig(
        admin_email=(os.getenv("ADMIN_EMAIL") or "").strip().lower(),
        admin_password_hash=(os.getenv("ADMIN_PASSWORD_HASH") or "").strip(),
        jwt_secret=(os.getenv("JWT_SECRET") or "").strip(),
        jwt_algorithm=(os.getenv("JWT_ALGORITHM") or "HS256").strip(),
        jwt_expires_minutes=int(os.getenv("JWT_EXPIRES_MINUTES") or "720"),
    )


# ── Models ───────────────────────────────────────────────────────────────────


class CurrentUser(BaseModel):
    email: str
    role: str = "admin"


# ── Password hashing ─────────────────────────────────────────────────────────


def hash_password(plain: str) -> str:
    return bcrypt.hashpw(_to_bcrypt_bytes(plain), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(_to_bcrypt_bytes(plain), hashed.encode("utf-8"))
    except (ValueError, TypeError) as exc:
        logger.warning("Password verify failed: %s", exc)
        return False


# ── JWT ──────────────────────────────────────────────────────────────────────


def create_access_token(subject: str, *, extra: Optional[dict] = None) -> str:
    cfg = get_auth_config()
    if not cfg.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured.")

    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": subject,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=cfg.jwt_expires_minutes)).timestamp()),
        "role": "admin",
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, cfg.jwt_secret, algorithm=cfg.jwt_algorithm)


def decode_token(token: str) -> dict:
    cfg = get_auth_config()
    if not cfg.jwt_secret:
        raise RuntimeError("JWT_SECRET is not configured.")
    return jwt.decode(token, cfg.jwt_secret, algorithms=[cfg.jwt_algorithm])


# ── FastAPI dependency ───────────────────────────────────────────────────────


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(_bearer_scheme),
) -> CurrentUser:
    """FastAPI dependency: validates the Bearer token and returns the user."""

    cfg = get_auth_config()
    if not cfg.configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Auth is not configured on the server. "
                "Set ADMIN_EMAIL, ADMIN_PASSWORD_HASH, and JWT_SECRET."
            ),
        )

    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing bearer token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_token(credentials.credentials)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    subject = (payload.get("sub") or "").strip().lower()
    if not subject or subject != cfg.admin_email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token does not match a known user.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(email=subject, role=payload.get("role", "admin"))


__all__ = [
    "AuthConfig",
    "CurrentUser",
    "create_access_token",
    "decode_token",
    "get_auth_config",
    "get_current_user",
    "hash_password",
    "verify_password",
]
