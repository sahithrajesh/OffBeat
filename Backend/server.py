"""FastAPI server with Spotify OAuth endpoints.

Endpoints
---------
GET  /auth/login     → redirect user to Spotify
GET  /auth/callback  → handle Spotify redirect, issue JWT, redirect to frontend
GET  /auth/me        → return current user info (requires JWT)

GET  /playlists      → fetch the user's Spotify playlists (requires JWT)

(When behind Traefik, these are accessible at /api/* paths)

All protected routes use the ``require_auth`` dependency to extract the
Spotify user ID from the JWT.

Run with::

    uvicorn server:app --host 0.0.0.0 --port 8888 --reload
"""

from __future__ import annotations

import secrets
import logging
from dataclasses import asdict
from typing import Optional

from fastapi import FastAPI, Depends, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
import uvicorn

import config
import cache
from models import (
    Playlist,
    EnrichedTrack,
    EnrichedPlaylist,
    AnalysisOutput,
    AnalysisSummary,
    AnalysisCluster,
    AnalysisCentroidFeatures,
    AnalysisTrackRow,
    AnalysisTrackRef,
    MoodEntry,
)
from spotify_auth import build_authorize_url, exchange_code, get_spotify_user
from spotify_client import get_user_playlists
from pocketbase_client import upsert_user, get_valid_access_token, get_user
from session import create_session_token, verify_session_token

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
    redirect_url = f"{config.FRONTEND_URL}/auth/callback?token={jwt_token}"
    return RedirectResponse(redirect_url)


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

    return [
        Playlist(
            spotify_id=p["id"],
            name=p["name"],
            total_tracks=p.get("tracks", {}).get("total", 0),
            owner=p.get("owner", {}).get("display_name", ""),
            description=p.get("description"),
            image_url=p.get("images", [{}])[0].get("url") if p.get("images") else None,
        )
        for p in playlists
    ]


@app.post("/create")
async def create_playlist(
    tracks: list[EnrichedTrack],
    spotify_id: str = Depends(require_auth),
):
    """Create a Spotify playlist from a list of enriched tracks."""
    # TODO: Implement playlist creation logic
    # - Get access token
    # - Create new playlist via Spotify API
    # - Add tracks to playlist
    # - Return playlist info
    raise HTTPException(status_code=501, detail="Not implemented")


@app.post("/analysis")
async def analyze_playlists(
    playlists: list[Playlist],
    spotify_id: str = Depends(require_auth),
):
    """Analyze playlists and return analysis data."""
    # TODO: Implement analysis logic
    # - Process playlist data
    # - Generate analysis metrics
    # - Return unmodeled data (dict)
    raise HTTPException(status_code=501, detail="Not implemented")


@app.post("/compare")
async def compare_playlist(
    analysis_data: dict,
    playlist: Playlist,
    spotify_id: str = Depends(require_auth),
):
    """Compare a playlist against analysis data."""
    # TODO: Implement comparison logic
    # - Process analysis data and playlist
    # - Generate comparison metrics
    # - Return unmodeled data (dict)
    raise HTTPException(status_code=501, detail="Not implemented")


@app.post("/basic", response_model=EnrichedPlaylist)
async def basic_playlist(
    analysis_data: dict,
    spotify_id: str = Depends(require_auth),
):
    """Generate a basic playlist from analysis data."""
    # TODO: Implement basic playlist generation logic
    # - Process analysis data
    # - Select tracks based on basic criteria
    # - Return EnrichedPlaylist
    raise HTTPException(status_code=501, detail="Not implemented")


@app.post("/anomaly", response_model=EnrichedPlaylist)
async def anomaly_playlist(
    analysis_data: dict,
    spotify_id: str = Depends(require_auth),
):
    """Generate an anomaly-based playlist from analysis data."""
    # TODO: Implement anomaly detection logic
    # - Process analysis data
    # - Detect anomalous tracks
    # - Return EnrichedPlaylist
    raise HTTPException(status_code=501, detail="Not implemented")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    uvicorn.run("server:app", host="0.0.0.0", port=8888, reload=True)
