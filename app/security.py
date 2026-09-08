import hashlib
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings


def hash_password(password: str) -> str:
    # bcrypt operates on at most 72 bytes; truncate defensively.
    pw = password.encode("utf-8")[:72]
    return bcrypt.hashpw(pw, bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(
            password.encode("utf-8")[:72], hashed.encode("utf-8")
        )
    except ValueError:
        return False


def create_access_token(subject: str, role: str = "user") -> str:
    """Issue an access token.

    ``role`` separates the two audiences: "user" for the customer app and
    "partner" for the partner app. Customers and partners live in different
    tables, so without this claim a token from one app would be presented to
    the other's endpoints and only fail by id lookup — the claim makes the
    rejection explicit.
    """
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )
    payload = {"sub": subject, "exp": expire, "type": "access", "role": role}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def decode_access_token(token: str, *, expected_role: str = "user") -> str | None:
    """Return the subject if the token is valid for ``expected_role``, else None."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    # Tokens issued before roles existed carry no claim; they're all customers.
    if payload.get("role", "user") != expected_role:
        return None
    return payload.get("sub")


def generate_reset_code() -> str:
    """A 6-digit numeric one-time code (e.g. '048217')."""
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_reset_code(code: str) -> str:
    return hashlib.sha256(code.encode("utf-8")).hexdigest()
