"""Spotify Authorization Code flow.

Opens a temporary local web server on the redirect-URI port, launches the
user's browser to Spotify's /authorize endpoint, waits for the callback,
exchanges the authorization code for an access token, and returns the token.
"""

from __future__ import annotations

import asyncio
import secrets
import webbrowser
from urllib.parse import urlencode, urlparse, parse_qs

from aiohttp import web, ClientSession

import config

# Scopes needed to read the user's playlists and their tracks.
SCOPES = "playlist-read-private playlist-read-collaborative"

SPOTIFY_AUTH_URL = "https://accounts.spotify.com/authorize"
SPOTIFY_TOKEN_URL = "https://accounts.spotify.com/api/token"


async def authenticate() -> str:
    """Run the full auth-code flow and return a Spotify access token.

    1. Start a lightweight HTTP server on the redirect URI port.
    2. Open the browser so the user can log in / approve.
    3. Receive the callback, extract the ``code``.
    4. Exchange the code for an access token.
    5. Shut down the server and return the token.
    """

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
            return body["access_token"]
