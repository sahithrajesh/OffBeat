"""JWT session tokens for frontend ↔ backend authentication.

The frontend receives a short-lived JWT after the Spotify OAuth callback.
It stores the JWT (e.g. in localStorage) and sends it on every request as::

    Authorization: Bearer <jwt>

The JWT payload contains only the Spotify user ID — all sensitive data
(Spotify tokens) stays in PocketBase on the server.
"""

from __future__ import annotations

import time
from typing import Optional

import jwt  # PyJWT

import config

_ALGORITHM = "HS256"
_DEFAULT_TTL = 60 * 60 * 24 * 7  # 7 days


def create_session_token(
    spotify_id: str,
    display_name: str,
    ttl: int = _DEFAULT_TTL,
) -> str:
    """Create a signed JWT for the given user."""
    now = int(time.time())
    payload = {
        "sub": spotify_id,
        "name": display_name,
        "iat": now,
        "exp": now + ttl,
    }
    return jwt.encode(payload, config.JWT_SECRET, algorithm=_ALGORITHM)


def verify_session_token(token: str) -> Optional[dict]:
    """Verify and decode a JWT.

    Returns the decoded payload dict on success, or None if the token
    is invalid / expired.
    """
    try:
        return jwt.decode(token, config.JWT_SECRET, algorithms=[_ALGORITHM])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None


def get_spotify_id(token: str) -> Optional[str]:
    """Convenience: extract the Spotify user ID from a JWT, or None."""
    payload = verify_session_token(token)
    return payload["sub"] if payload else None
