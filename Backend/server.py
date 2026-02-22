"""FastAPI server with Spotify OAuth endpoints.

Endpoints
---------
GET  /auth/login     → redirect user to Spotify
GET  /auth/callback  → handle Spotify redirect, issue JWT, redirect to frontend
GET  /auth/me        → return current user info (requires JWT)

GET  /playlists      → fetch the user's Spotify playlists (requires JWT)
POST /analysis       → enrich + analyse selected playlists
POST /compare        → compare a playlist against analysis data
POST /basic          → generate a basic playlist from analysis data
POST /anomaly        → generate an anomaly-based playlist
POST /create         → create a Spotify playlist from enriched tracks

All protected routes use the ``require_auth`` dependency to extract the
Spotify user ID from the JWT.  Enrichment (Spotify track fetch + ReccoBeats
+ Last.fm) happens transparently — the frontend never calls /enrich.

Run with::

    uvicorn server:app --host 0.0.0.0 --port 8888 --reload
"""

from __future__ import annotations

import secrets
import logging
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import uvicorn

import config
import cache
from models import Playlist, EnrichedTrack, EnrichedPlaylist
from spotify_auth import build_authorize_url, exchange_code, get_spotify_user
from spotify_client import get_user_playlists
from enricher import enrich_playlists
from pocketbase_client import upsert_user, get_valid_access_token, get_user
from session import create_session_token, verify_session_token

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
)
# Silence noisy HTTP libraries
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)

# In-memory state store (for CSRF protection during OAuth).
# For a hackathon this is fine; production would use Redis / DB.
_pending_states: set[str] = set()


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(title="Hacklytics 2026 API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[config.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Middleware to log incoming requests
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log incoming request path for debugging."""
    logger.info(f"[request] {request.method} {request.url.path}")
    response = await call_next(request)
    return response


# ---------------------------------------------------------------------------
# Auth dependency
# ---------------------------------------------------------------------------

async def require_auth(request: Request) -> str:
    """FastAPI dependency that validates the JWT and returns the spotify_id.

    Raises 401 if the token is missing or invalid.
    """
    auth = request.headers.get("Authorization", "")
    token: Optional[str] = auth[7:] if auth.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Missing or invalid session token")
    payload = verify_session_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Missing or invalid session token")
    return payload["sub"]


# ---------------------------------------------------------------------------
# Auth routes
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    """Health check / root endpoint."""
    return {
        "status": "ok",
        "service": "Hacklytics 2026 API",
        "docs": "/docs",
    }


@app.get("/auth/login")
async def login():
    """Redirect to Spotify authorize page."""
    state = secrets.token_urlsafe(16)
    _pending_states.add(state)
    url = build_authorize_url(state)
    return RedirectResponse(url)


@app.get("/auth/callback")
async def callback(
    code: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
):
    """Handle Spotify redirect after user approves."""
    if error:
        raise HTTPException(status_code=400, detail=f"Spotify auth error: {error}")

    if not state or state not in _pending_states:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    _pending_states.discard(state)

    if not code:
        raise HTTPException(status_code=400, detail="Missing authorization code")

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
    redirect_url = f"{config.FRONTEND_URL}/home?token={jwt_token}"
    return RedirectResponse(redirect_url, status_code=302)


@app.get("/auth/me")
async def me(spotify_id: str = Depends(require_auth)):
    """Return current user profile (requires JWT)."""
    user = await get_user(spotify_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "spotify_id": user["spotify_id"],
        "display_name": user["display_name"],
        "email": user.get("email", ""),
        "avatar_url": user.get("avatar_url", ""),
    }


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/playlists", response_model=list[Playlist])
async def my_playlists(spotify_id: str = Depends(require_auth)):
    """Fetch the user's Spotify playlists."""
    access_token = await get_valid_access_token(spotify_id)  # auto-refreshes
    playlists = await get_user_playlists(access_token)

    results = []
    for p in playlists:
        tracks_field = p.get("tracks")
        if isinstance(tracks_field, dict):
            track_count = tracks_field.get("total", 0)
        elif isinstance(tracks_field, int):
            track_count = tracks_field
        else:
            track_count = 0
        # Prefer the explicit root-level field if present
        track_count = p.get("total_tracks", track_count) or track_count

        images = p.get("images") or []
        image_url = images[0].get("url") if images else None

        results.append(
            Playlist(
                spotify_id=p["id"],
                name=p["name"],
                total_tracks=track_count,
                owner=p.get("owner", {}).get("display_name", ""),
                description=p.get("description"),
                image_url=image_url,
            )
        )
    return results


# ---------------------------------------------------------------------------
# Internal enrichment helper
# ---------------------------------------------------------------------------

async def _get_enriched_playlists(
    spotify_id: str,
    playlist_ids: list[str],
) -> list[EnrichedPlaylist]:
    """Return enriched playlists, using cache where possible.

    This is the single internal entry point that every endpoint calls.
    It handles:
      1. Fetching the user's Spotify access token (auto-refresh).
      2. Checking snapshot_ids to skip unchanged playlists.
      3. Enriching only what's needed (cache-aware, per-track dedup).
      4. Persisting results back to PocketBase.

    The frontend never sees this — it just calls an endpoint with playlist
    IDs and gets results.
    """
    access_token = await get_valid_access_token(spotify_id)

    # Lightweight playlist listing to get snapshot_ids
    all_playlists = await get_user_playlists(access_token)
    playlist_map = {p["id"]: p for p in all_playlists}

    cached: list[EnrichedPlaylist] = []
    to_fetch: list[dict] = []

    for pid in playlist_ids:
        raw = playlist_map.get(pid)
        if raw is None:
            logger.warning(f"Playlist {pid} not found in user's library, skipping.")
            continue

        current_snapshot = raw.get("snapshot_id", "")
        cached_snapshot = await cache.get_snapshot_id(spotify_id, pid)

        if cached_snapshot and cached_snapshot == current_snapshot:
            hit = await cache.get(spotify_id, pid)
            if hit:
                cached.append(hit)
                logger.info(f"Cache hit for playlist {pid} (snapshot unchanged)")
                continue

        to_fetch.append(raw)

    newly_enriched: list[EnrichedPlaylist] = []
    if to_fetch:
        logger.info(f"Enriching {len(to_fetch)} playlist(s)…")
        newly_enriched = await enrich_playlists(access_token, to_fetch)
        for ep in newly_enriched:
            raw = playlist_map.get(ep.spotify_id, {})
            ep.snapshot_id = raw.get("snapshot_id", "")
            await cache.put(spotify_id, ep)

    return cached + newly_enriched


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@app.get("/playlists", response_model=list[Playlist])
async def my_playlists(spotify_id: str = Depends(require_auth)):
    """Fetch the user's Spotify playlists."""
    access_token = await get_valid_access_token(spotify_id)  # auto-refreshes
    playlists = await get_user_playlists(access_token)

    results = []
    for p in playlists:
        tracks_field = p.get("tracks")
        if isinstance(tracks_field, dict):
            track_count = tracks_field.get("total", 0)
        elif isinstance(tracks_field, int):
            track_count = tracks_field
        else:
            track_count = 0
        track_count = p.get("total_tracks", track_count) or track_count

        images = p.get("images") or []
        image_url = images[0].get("url") if images else None

        results.append(
            Playlist(
                spotify_id=p["id"],
                name=p["name"],
                total_tracks=track_count,
                owner=p.get("owner", {}).get("display_name", ""),
                description=p.get("description"),
                image_url=image_url,
            )
        )
    return results


@app.post("/analysis")
async def analyze_playlists(
    playlist_ids: list[str],
    spotify_id: str = Depends(require_auth),
):
    """Analyse selected playlists.

    Enrichment happens transparently — just send playlist IDs.
    """
    enriched = await _get_enriched_playlists(spotify_id, playlist_ids)
    if not enriched:
        raise HTTPException(status_code=404, detail="No playlists found to analyse.")
    # TODO: Implement analysis logic using `enriched`
    raise HTTPException(status_code=501, detail="Not implemented")


@app.post("/compare")
async def compare_playlist(
    analysis_data: dict,
    playlist_id: str,
    spotify_id: str = Depends(require_auth),
):
    """Compare a playlist against analysis data.

    The playlist is enriched transparently if not already cached.
    """
    enriched = await _get_enriched_playlists(spotify_id, [playlist_id])
    if not enriched:
        raise HTTPException(status_code=404, detail=f"Playlist {playlist_id} not found.")
    # TODO: Implement comparison logic using `enriched[0]` + `analysis_data`
    raise HTTPException(status_code=501, detail="Not implemented")


@app.post("/basic", response_model=EnrichedPlaylist)
async def basic_playlist(
    analysis_data: dict,
    spotify_id: str = Depends(require_auth),
):
    """Generate a basic playlist from analysis data."""
    # TODO: Implement basic playlist generation logic
    raise HTTPException(status_code=501, detail="Not implemented")


@app.post("/anomaly", response_model=EnrichedPlaylist)
async def anomaly_playlist(
    analysis_data: dict,
    spotify_id: str = Depends(require_auth),
):
    """Generate an anomaly-based playlist from analysis data."""
    # TODO: Implement anomaly detection logic
    raise HTTPException(status_code=501, detail="Not implemented")


@app.post("/create")
async def create_playlist(
    tracks: list[EnrichedTrack],
    spotify_id: str = Depends(require_auth),
):
    """Create a Spotify playlist from a list of enriched tracks."""
    # TODO: Implement playlist creation logic
    raise HTTPException(status_code=501, detail="Not implemented")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _enriched_playlist_to_dict(ep: EnrichedPlaylist) -> dict:
    """Convert an EnrichedPlaylist dataclass to a JSON-safe dict."""
    from dataclasses import asdict
    return asdict(ep)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8888, reload=True)
