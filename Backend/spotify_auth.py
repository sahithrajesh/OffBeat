"""Spotify Authorization Code flow.

Provides two modes:
1. **Web flow** (for frontend integration): generate the auth URL and exchange
   a callback code for tokens via standalone helpers.
2. **Interactive flow** (legacy): opens a local server + browser for CLI usage.

Both modes return the full token payload (access_token, refresh_token, etc.)
and can fetch the current user's Spotify profile.
"""

from __future__ import annotations

import asyncio
import secrets
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs
from typing import Any

from aiohttp import web, ClientSession

import config

# Scopes needed to read the user's playlists and their tracks.
SCOPES = "playlist-read-private playlist-read-collaborative"

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"
SPOTIFY_ME_URL = "https://api.spotify.com/v1/me"


# ---------------------------------------------------------------------------
# Web-flow helpers (used by the API server)
# ---------------------------------------------------------------------------

def build_authorize_url(state: str) -> str:
    """Return the Spotify authorize URL the frontend should redirect to."""
    params = urlencode(
        {
            "client_id": config.SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": config.SPOTIFY_REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
        }
    )
    return f"{SPOTIFY_AUTH_URL}?{params}"


async def exchange_code(code: str) -> dict[str, Any]:
    """Exchange an authorization *code* for a token payload.

    Returns the full Spotify response which includes at least::

        {
            "access_token": "...",
            "token_type": "Bearer",
            "scope": "...",
            "expires_in": 3600,
            "refresh_token": "..."
        }
    """
    async with ClientSession() as session:
        async with session.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": config.SPOTIFY_REDIRECT_URI,
                "client_id": config.SPOTIFY_CLIENT_ID,
                "client_secret": config.SPOTIFY_CLIENT_SECRET,
            },
        ) as resp:
            body = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"Token exchange failed: {body}")
            return body


async def refresh_access_token(refresh_token: str) -> dict[str, Any]:
    """Use a refresh token to obtain a new access token from Spotify."""
    async with ClientSession() as session:
        async with session.post(
            SPOTIFY_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": config.SPOTIFY_CLIENT_ID,
                "client_secret": config.SPOTIFY_CLIENT_SECRET,
            },
        ) as resp:
            body = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"Token refresh failed: {body}")
            return body


async def get_spotify_user(access_token: str) -> dict[str, Any]:
    """Fetch the current user's Spotify profile (/v1/me)."""
    async with ClientSession() as session:
        async with session.get(
            SPOTIFY_ME_URL,
            headers={"Authorization": f"Bearer {access_token}"},
        ) as resp:
            body = await resp.json()
            if resp.status != 200:
                raise RuntimeError(f"Failed to fetch profile: {body}")
            return body


# ---------------------------------------------------------------------------
# Interactive / CLI flow (kept for local development & notebooks)
# ---------------------------------------------------------------------------

async def authenticate() -> str:
    """Run the full auth-code flow interactively and return a Spotify access token."""

    parsed = urlparse(config.SPOTIFY_REDIRECT_URI)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8888
    callback_path = parsed.path or "/callback"

    # We'll resolve this future when the callback arrives.
    code_future: asyncio.Future[str] = asyncio.get_event_loop().create_future()
    state = secrets.token_urlsafe(16)

    # ---- callback handler ----
    async def _handle_callback(request: web.Request) -> web.Response:
        error = request.query.get("error")
        if error:
            code_future.set_exception(RuntimeError(f"Spotify auth error: {error}"))
            return web.Response(
                text="Authorization failed. You can close this tab.",
                content_type="text/html",
            )

        returned_state = request.query.get("state", "")
        if returned_state != state:
            code_future.set_exception(
                RuntimeError("State mismatch – possible CSRF attack.")
            )
            return web.Response(text="State mismatch.", content_type="text/html")

        code = request.query.get("code", "")
        if not code:
            code_future.set_exception(RuntimeError("No code in callback."))
            return web.Response(text="Missing code.", content_type="text/html")

        code_future.set_result(code)
        return web.Response(
            text="<h3>Authorization successful!</h3><p>You can close this tab and return to the app.</p>",
            content_type="text/html",
        )

    # ---- start server ----
    app = web.Application()
    app.router.add_get(callback_path, _handle_callback)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host, port)
    await site.start()

    # ---- open browser ----
    params = urlencode(
        {
            "client_id": config.SPOTIFY_CLIENT_ID,
            "response_type": "code",
            "redirect_uri": config.SPOTIFY_REDIRECT_URI,
            "scope": SCOPES,
            "state": state,
        }
    )
    auth_url = f"{SPOTIFY_AUTH_URL}?{params}"
    print(f"\nOpening browser for Spotify login…\n  {auth_url}\n")
    webbrowser.open(auth_url)

    # ---- wait for the callback ----
    try:
        code = await code_future
    finally:
        await runner.cleanup()

    # ---- exchange code for token ----
    token_data = await exchange_code(code)
    return token_data["access_token"]
