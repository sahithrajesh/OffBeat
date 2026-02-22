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
POST /sphinx         → ask SphinxAI a question about your playlists
POST /sphinx/reset   → reset SphinxAI session

All protected routes use the ``require_auth`` dependency to extract the
Spotify user ID from the JWT.  Enrichment (Spotify track fetch + ReccoBeats
+ Last.fm) happens transparently — the frontend never calls /enrich.

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
from spotify_client import get_user_playlists, create_new_playlist, add_tracks_to_playlist
from enricher import enrich_playlists
from pocketbase_client import upsert_user, get_valid_access_token, get_user
from session import create_session_token, verify_session_token
from reccobeats_client import get_cluster_recommendations
from analysis import (
    run_playlist_analysis,
    run_playlists_analysis,
    compare_playlists as compare_playlists_analysis,
    select_tracks_by_mood,
    analysis_output_to_dict,
    clear_cache as clear_analysis_cache,
)
from sphinx_chat import run_sphinx, destroy_session as destroy_sphinx_session, shutdown_jupyter_server

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


@app.on_event("shutdown")
def _shutdown():
    shutdown_jupyter_server()


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
    frontend_base = config.FRONTEND_URL.rstrip("/")
    redirect_url = f"{frontend_base}/home?token={jwt_token}"
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
    """Analyse selected playlists (full pipeline).

    Accepts a list of Spotify playlist IDs from the frontend.
    Enrichment happens transparently, then clustering + anomaly
    detection runs in-process via the ``analysis`` module.

    Returns per-playlist analysis (clusters, moods, anomalies, summary).
    """
    enriched = await _get_enriched_playlists(spotify_id, playlist_ids)
    if not enriched:
        raise HTTPException(status_code=404, detail="No playlists found to analyse.")

    analyses = run_playlists_analysis(enriched)
    return {
        "num_playlists": len(analyses),
        "playlists": [analysis_output_to_dict(a) for a in analyses],
    }


@app.post("/compare")
async def compare_playlist(
    playlist_ids: list[str],
    spotify_id: str = Depends(require_auth),
):
    """Compare multiple playlists by mood distribution.

    Requires at least 2 playlist IDs.  Enrichment + analysis happen
    transparently.
    """
    enriched = await _get_enriched_playlists(spotify_id, playlist_ids)
    if len(enriched) < 2:
        raise HTTPException(
            status_code=400,
            detail="At least 2 playlists are required for comparison.",
        )
    return compare_playlists_analysis(enriched)


@app.post("/basic")
async def basic_playlist(
    playlist_ids: list[str],
    spotify_id: str = Depends(require_auth),
):
    """Generate cluster-based recommendations from aggregated analysis.

    When multiple playlists are selected, all tracks are aggregated
    together and analyzed as a single corpus, then recommendations are
    generated from that combined analysis. This is faster and produces
    more cohesive recommendations compared to per-playlist analysis.

    Accepts a list of Spotify playlist IDs.  Enrichment + analysis happen
    transparently, then for each cluster, seeds are sent in groups of 5
    to the ReccoBeats recommendation API (5:1 ratio).
    """
    enriched = await _get_enriched_playlists(spotify_id, playlist_ids)
    if not enriched:
        raise HTTPException(status_code=404, detail="No playlists found.")

    # Aggregate all playlists into a single virtual playlist for unified analysis
    # Deduplicate tracks across playlists by spotify_id to avoid
    # duplicate DataFrame indices in the analysis pipeline.
    seen_ids: set[str] = set()
    unique_tracks: list[EnrichedTrack] = []
    for pl in enriched:
        for t in (pl.tracks or []):
            if t.spotify_id not in seen_ids:
                seen_ids.add(t.spotify_id)
                unique_tracks.append(t)

    aggregated_playlist = EnrichedPlaylist(
        spotify_id="aggregated",
        name="Aggregated Playlists",
        tracks=unique_tracks,
        total_tracks=len(unique_tracks),
    )

    # Run analysis once on the aggregated playlist (much faster than per-playlist)
    analysis = run_playlist_analysis(aggregated_playlist, use_cache=False)
    
    # Convert to the dict format get_cluster_recommendations expects
    clusters_dict = {}
    for c in analysis.clusters:
        clusters_dict[c.label] = {
            "cluster_id": c.cluster_id,
            "size": c.size,
            "centroid_features": {
                "audio_means": c.centroid_features.audio_means,
                "top_tags": c.centroid_features.top_tags,
                "tag_weights_top": c.centroid_features.tag_weights_top,
            },
            "tracks": [
                {
                    "spotify_id": t.spotify_id,
                    "title": t.title,
                    "is_anomaly": t.is_anomaly,
                }
                for t in c.tracks
            ],
        }
    
    analysis_data = {
        "playlists": [
            {
                "playlist_id": "aggregated",
                "playlist_name": "Aggregated Playlists",
                "clusters": clusters_dict,
            }
        ]
    }

    try:
        recommendations = await get_cluster_recommendations(analysis_data)
    except Exception as e:
        logger.exception("Recommendation generation failed")
        raise HTTPException(status_code=500, detail=f"Recommendation error: {e}")

    if not recommendations:
        raise HTTPException(status_code=404, detail="No clusters found in analysis data.")

    return recommendations


@app.post("/anomaly")
async def anomaly_playlist(
    playlist_ids: list[str],
    spotify_id: str = Depends(require_auth),
):
    """Return anomaly tracks across the selected playlists.

    Enrichment + analysis happen transparently.  Returns the anomaly
    tracks from each playlist's analysis.
    """
    enriched = await _get_enriched_playlists(spotify_id, playlist_ids)
    if not enriched:
        raise HTTPException(status_code=404, detail="No playlists found.")

    all_anomalies: list[dict] = []
    for pl in enriched:
        analysis = run_playlist_analysis(pl)
        for cluster in analysis.clusters:
            for tr in cluster.tracks:
                if tr.is_anomaly:
                    all_anomalies.append({
                        "spotify_id": tr.spotify_id,
                        "title": tr.title,
                        "cluster_id": tr.cluster_id,
                        "anomaly_score": tr.anomaly_score,
                        "reason": tr.reason,
                        "playlist_id": pl.spotify_id,
                        "playlist_name": pl.name,
                    })

    all_anomalies.sort(key=lambda x: x.get("anomaly_score") or 0, reverse=True)
    return {"anomalies": all_anomalies, "count": len(all_anomalies)}


@app.post("/create")
async def create_playlist_endpoint(
    track_ids: list[str],
    spotify_id: str = Depends(require_auth),
):
    """Create a Spotify playlist from a list of Spotify track IDs."""
    if not track_ids:
        raise HTTPException(status_code=400, detail="No tracks provided.")

    # 1. Grab the fresh token
    access_token = await get_valid_access_token(spotify_id)
    
    try:
        # 2. Create the empty playlist
        playlist_id = await create_new_playlist(
            token=access_token,
            user_id=spotify_id,
            name="OffBeat AI Selection",
            description="A custom playlist generated by OffBeat AI."
        )
        
        # 3. Format tracks as Spotify URIs and push them
        track_uris = [f"spotify:track:{tid}" for tid in track_ids]
        await add_tracks_to_playlist(access_token, playlist_id, track_uris)
        
        return {
            "status": "success", 
            "playlist_id": playlist_id,
            "url": f"https://open.spotify.com/playlist/{playlist_id}"
        }
        
    except Exception as e:
        logger.error(f"Failed to create playlist: {e}")
        raise HTTPException(status_code=500, detail="Failed to save playlist to Spotify.")



# ---------------------------------------------------------------------------
# Sphinx AI chatbot
# ---------------------------------------------------------------------------

from pydantic import BaseModel

class SphinxChatRequest(BaseModel):
    playlist_ids: list[str]
    prompt: str
    action_context: Optional[dict] = None  # current action type + result summary


@app.post("/sphinx")
async def sphinx_chat(
    body: SphinxChatRequest,
    spotify_id: str = Depends(require_auth),
):
    """Ask SphinxAI a question about your playlists.

    The first request creates a notebook session seeded with the user's
    enriched + analysed data.  Follow-up questions reuse the same notebook
    so Sphinx has full conversation context.
    """
    if not body.prompt.strip():
        raise HTTPException(status_code=400, detail="Prompt cannot be empty.")

    enriched = await _get_enriched_playlists(spotify_id, body.playlist_ids)
    if not enriched:
        raise HTTPException(status_code=404, detail="No playlists found.")

    # Run analysis so Sphinx has cluster/anomaly context
    analyses = run_playlists_analysis(enriched)

    result = await run_sphinx(
        user_id=spotify_id,
        prompt=body.prompt,
        enriched=enriched,
        analyses=analyses,
        action_context=body.action_context,
        timeout_seconds=120,
    )
    return result


@app.post("/sphinx/reset")
async def sphinx_reset(spotify_id: str = Depends(require_auth)):
    """Reset the user's SphinxAI session (clears notebook context)."""
    destroy_sphinx_session(spotify_id)
    return {"status": "ok"}


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
