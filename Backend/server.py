"""aiohttp API server with Spotify OAuth endpoints.

Endpoints
---------
GET  /auth/login     → redirect user to Spotify
GET  /auth/callback  → handle Spotify redirect, issue JWT, redirect to frontend
GET  /auth/me        → return current user info (requires JWT)
POST /auth/logout    → (optional) frontend just discards its JWT

All other API routes should use the ``require_auth`` middleware/helper to
extract the Spotify user ID from the JWT.

Run with::

    python server.py
"""

from __future__ import annotations

import secrets
from typing import Optional

from aiohttp import web
from aiohttp.web import middleware
import aiohttp_cors

import config
from spotify_auth import build_authorize_url, exchange_code, get_spotify_user
from pocketbase_client import upsert_user, get_valid_access_token, get_user
from session import create_session_token, verify_session_token

# In-memory state store (for CSRF protection during OAuth).
# For a hackathon this is fine; production would use Redis / DB.
_pending_states: set[str] = set()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _extract_token(request: web.Request) -> Optional[str]:
    """Pull the JWT from the Authorization header."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return None


def _get_spotify_id(request: web.Request) -> Optional[str]:
    """Validate the JWT and return the spotify_id, or None."""
    token = _extract_token(request)
    if not token:
        return None
    payload = verify_session_token(token)
    return payload["sub"] if payload else None


async def require_auth(request: web.Request) -> str:
    """Helper that raises 401 if the request is not authenticated.

    Returns the spotify_id on success.
    """
    spotify_id = _get_spotify_id(request)
    if not spotify_id:
        raise web.HTTPUnauthorized(text="Missing or invalid session token")
    return spotify_id


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

async def login(request: web.Request) -> web.Response:
    """GET /auth/login — redirect to Spotify authorize page."""
    state = secrets.token_urlsafe(16)
    _pending_states.add(state)
    url = build_authorize_url(state)
    raise web.HTTPFound(url)


async def callback(request: web.Request) -> web.Response:
    """GET /auth/callback — Spotify redirects here after user approves."""
    error = request.query.get("error")
    if error:
        raise web.HTTPBadRequest(text=f"Spotify auth error: {error}")

    state = request.query.get("state", "")
    if state not in _pending_states:
        raise web.HTTPBadRequest(text="Invalid state parameter")
    _pending_states.discard(state)

    code = request.query.get("code", "")
    if not code:
        raise web.HTTPBadRequest(text="Missing authorization code")

    # Exchange code for tokens
    token_data = await exchange_code(code)

    # Fetch Spotify profile
    profile = await get_spotify_user(token_data["access_token"])
    spotify_id = profile["id"]
    display_name = profile.get("display_name", spotify_id)
    email = profile.get("email")
    images = profile.get("images", [])
    avatar_url = images[0]["url"] if images else None

    # Upsert user + tokens in PocketBase
    await upsert_user(
        spotify_id=spotify_id,
        display_name=display_name,
        email=email,
        avatar_url=avatar_url,
        access_token=token_data["access_token"],
        refresh_token=token_data["refresh_token"],
        expires_in=token_data.get("expires_in", 3600),
    )

    # Create a session JWT for the frontend
    jwt_token = create_session_token(spotify_id, display_name)

    # Redirect to frontend with the JWT as a query param.
    # The frontend should grab it from the URL, store it, and clear the URL.
    redirect_url = f"{config.FRONTEND_URL}/auth/callback?token={jwt_token}"
    raise web.HTTPFound(redirect_url)


async def me(request: web.Request) -> web.Response:
    """GET /auth/me — return current user profile (requires JWT)."""
    spotify_id = await require_auth(request)
    user = await get_user(spotify_id)
    if not user:
        raise web.HTTPNotFound(text="User not found")

    return web.json_response(
        {
            "spotify_id": user["spotify_id"],
            "display_name": user["display_name"],
            "email": user.get("email", ""),
            "avatar_url": user.get("avatar_url", ""),
        }
    )


# ---------------------------------------------------------------------------
# Example protected route
# ---------------------------------------------------------------------------

async def my_playlists(request: web.Request) -> web.Response:
    """GET /api/playlists — fetch the user's Spotify playlists."""
    from spotify_client import get_user_playlists

    spotify_id = await require_auth(request)
    access_token = await get_valid_access_token(spotify_id)  # auto-refreshes
    playlists = await get_user_playlists(access_token)

    return web.json_response(
        [
            {
                "id": p["id"],
                "name": p["name"],
                "total_tracks": p.get("tracks", {}).get("total", 0),
                "owner": p.get("owner", {}).get("display_name", ""),
            }
            for p in playlists
        ]
    )


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------

def create_app() -> web.Application:
    app = web.Application()

    # Auth routes
    app.router.add_get("/auth/login", login)
    app.router.add_get("/auth/callback", callback)
    app.router.add_get("/auth/me", me)

    # API routes
    app.router.add_get("/api/playlists", my_playlists)

    # CORS – allow the frontend origin
    cors = aiohttp_cors.setup(
        app,
        defaults={
            config.FRONTEND_URL: aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*",
            )
        },
    )
    for route in list(app.router.routes()):
        cors.add(route)

    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8888)
