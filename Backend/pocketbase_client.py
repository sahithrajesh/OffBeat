"""PocketBase client for user management using the official Python SDK.

PocketBase stores Spotify tokens server-side so the frontend never
sees them.  The ``users`` collection (use a *custom* collection, not the
built-in auth collection) should have these fields:

    spotify_id      (text, unique)   – Spotify user ID
    display_name    (text)           – Spotify display name
    email           (text, optional) – Spotify email
    avatar_url      (text, optional) – Spotify profile image
    access_token    (text)           – Spotify access token
    refresh_token   (text)           – Spotify refresh token
    token_expires   (number)         – Unix timestamp when access_token expires

Create the collection via the PocketBase Admin UI or auto-migrate.

Uses: https://pypi.org/project/pocketbase/
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from pocketbase import PocketBase
from pocketbase.utils import ClientResponseError

import config

_client = PocketBase(config.POCKETBASE_URL)
_COLLECTION = "spotify_users"
_admin_token_expires_at: float = 0.0


def _ensure_admin_auth(force: bool = False) -> None:
    """Authenticate as a PocketBase superuser if not already authenticated.

    The SDK stores the auth token on the client instance, but the token
    expires after a period (typically 24 hours). This function tracks the
    expiration time and reauthenticates when needed.

    Args:
        force: If True, force reauthentication even if token appears valid.
    """
    global _admin_token_expires_at
    
    # Check if we need to (re)authenticate:
    # 1. No token exists
    # 2. Token has expired (with 5-minute buffer)
    # 3. Force flag is set
    current_time = time.time()
    needs_auth = (
        not _client.auth_store.token
        or current_time >= (_admin_token_expires_at - 300)  # 5-minute buffer
        or force
    )
    
    if needs_auth:
        _client.collection("_superusers").auth_with_password(
            config.POCKETBASE_ADMIN_EMAIL,
            config.POCKETBASE_ADMIN_PASSWORD,
        )
        # PocketBase admin tokens typically expire after 24 hours
        # Set expiration to 23 hours from now to be safe
        _admin_token_expires_at = current_time + (23 * 3600)


def _with_retry(func, *args, **kwargs):
    """Execute a function with automatic reauthentication on auth failures.
    
    If the function raises a 401/403 auth error, reauthenticate and retry once.
    """
    try:
        return func(*args, **kwargs)
    except ClientResponseError as e:
        # If we get an auth error (401 Unauthorized or 403 Forbidden),
        # our admin token may have expired. Try reauthenticating once.
        if e.status in (401, 403):
            _ensure_admin_auth(force=True)
            return func(*args, **kwargs)
        raise


# ---------------------------------------------------------------------------
# Synchronous helpers (run inside asyncio.to_thread)
# ---------------------------------------------------------------------------

def _find_by_spotify_id_sync(spotify_id: str) -> Optional[dict[str, Any]]:
    """Query PocketBase for a record matching the given spotify_id."""
    _ensure_admin_auth()
    try:
        result = _with_retry(
            _client.collection(_COLLECTION).get_list,
            1, 1, {"filter": f'spotify_id="{spotify_id}"'}
        )
        if result.items:
            return _record_to_dict(result.items[0])
        return None
    except ClientResponseError as e:
        # Only catch non-auth errors here (auth errors handled by _with_retry)
        if e.status not in (401, 403):
            return None
        raise


def _upsert_user_sync(
    spotify_id: str,
    display_name: str,
    email: Optional[str],
    avatar_url: Optional[str],
    access_token: str,
    refresh_token: str,
    expires_in: int,
) -> dict[str, Any]:
    _ensure_admin_auth()
    token_expires = int(time.time()) + expires_in
    payload = {
        "spotify_id": spotify_id,
        "display_name": display_name,
        "email": email or "",
        "avatar_url": avatar_url or "",
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_expires": token_expires,
    }

    existing = _find_by_spotify_id_sync(spotify_id)
    if existing:
        record = _with_retry(
            _client.collection(_COLLECTION).update,
            existing["id"], payload
        )
    else:
        record = _with_retry(
            _client.collection(_COLLECTION).create,
            payload
        )
    return _record_to_dict(record)


def _update_tokens_sync(
    spotify_id: str,
    access_token: str,
    expires_in: int,
    refresh_token: Optional[str] = None,
) -> None:
    _ensure_admin_auth()
    existing = _find_by_spotify_id_sync(spotify_id)
    if not existing:
        raise RuntimeError(f"User {spotify_id} not found in PocketBase")

    payload: dict[str, Any] = {
        "access_token": access_token,
        "token_expires": int(time.time()) + expires_in,
    }
    if refresh_token:
        payload["refresh_token"] = refresh_token

    _with_retry(
        _client.collection(_COLLECTION).update,
        existing["id"], payload
    )


def _record_to_dict(record: Any) -> dict[str, Any]:
    """Convert a PocketBase record object to a plain dict."""
    # The SDK returns record objects with attribute access;
    # normalise to a dict so the rest of the code stays simple.
    if isinstance(record, dict):
        return record
    # The SDK record exposes .collection_id, .id, etc. and stores
    # user-defined fields in the object attributes.
    d: dict[str, Any] = {}
    for key in (
        "id", "spotify_id", "display_name", "email",
        "avatar_url", "access_token", "refresh_token", "token_expires",
    ):
        d[key] = getattr(record, key, None)
    return d


# ---------------------------------------------------------------------------
# Async public API (wraps sync SDK calls via to_thread)
# ---------------------------------------------------------------------------

async def upsert_user(
    spotify_id: str,
    display_name: str,
    email: Optional[str],
    avatar_url: Optional[str],
    access_token: str,
    refresh_token: str,
    expires_in: int,
) -> dict[str, Any]:
    """Create or update a user record in PocketBase.

    Returns the PocketBase record as a dict.
    """
    return await asyncio.to_thread(
        _upsert_user_sync,
        spotify_id, display_name, email, avatar_url,
        access_token, refresh_token, expires_in,
    )


async def get_user(spotify_id: str) -> Optional[dict[str, Any]]:
    """Fetch a user record by Spotify ID, or None if not found."""
    return await asyncio.to_thread(_find_by_spotify_id_sync, spotify_id)


async def update_tokens(
    spotify_id: str,
    access_token: str,
    expires_in: int,
    refresh_token: Optional[str] = None,
) -> None:
    """Update just the token fields for a user."""
    await asyncio.to_thread(
        _update_tokens_sync, spotify_id, access_token, expires_in, refresh_token,
    )


async def get_valid_access_token(spotify_id: str) -> str:
    """Return a valid Spotify access token, refreshing if needed.

    This is the main helper the rest of the backend should call before
    making Spotify API requests on behalf of a user.
    """
    from spotify_auth import refresh_access_token  # avoid circular import

    user = await get_user(spotify_id)
    if not user:
        raise RuntimeError(f"User {spotify_id} not found")

    # If the token is still valid (with a 60-second buffer), return it
    if user["token_expires"] > int(time.time()) + 60:
        return user["access_token"]

    # Otherwise, refresh
    token_data = await refresh_access_token(user["refresh_token"])
    await update_tokens(
        spotify_id=spotify_id,
        access_token=token_data["access_token"],
        expires_in=token_data["expires_in"],
        # Spotify may or may not return a new refresh token
        refresh_token=token_data.get("refresh_token"),
    )
    return token_data["access_token"]
