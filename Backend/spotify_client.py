"""Spotify Web API helpers – playlist listing and track fetching."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import ClientSession

from models import Artist, Track

SPOTIFY_API = "https://api.spotify.com/v1"

# Maximum retries when Spotify returns 429 (Too Many Requests).
_MAX_RETRIES = 5

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(name)s - %(levelname)s - %(message)s",
)


def _auth_header(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def get_user_playlists(
    token: str,
) -> list[dict]:
    """Return *all* of the current user's playlists (handles pagination).

    Each dict has at least ``id``, ``name``, ``tracks["total"]``,
    ``owner["display_name"]``.
    """
    playlists: list[dict] = []
    url: str | None = f"{SPOTIFY_API}/me/playlists?limit=50"
    cumulative_wait = 0

    async with ClientSession() as session:
        while url:
            for attempt in range(_MAX_RETRIES):
                try:
                    async with session.get(url, headers=_auth_header(token)) as resp:
                        if resp.status == 429:
                            retry_after = int(resp.headers.get("Retry-After", 1))
                            cumulative_wait += retry_after
                            logger.warning(
                                f"[playlists] Rate limited (429). Waiting {retry_after}s "
                                f"(attempt {attempt + 1}/{_MAX_RETRIES}, cumulative wait: {cumulative_wait}s)"
                            )
                            await asyncio.sleep(retry_after)
                            continue
                        
                        if resp.status != 200:
                            error_detail = await resp.text()
                            logger.error(
                                f"[playlists] HTTP {resp.status} error: {error_detail[:200]}"
                            )
                            resp.raise_for_status()
                        
                        data = await resp.json()
                except Exception as e:
                    logger.error(f"[playlists] Request failed: {type(e).__name__}: {e}")
                    if attempt < _MAX_RETRIES - 1:
                        await asyncio.sleep(2 ** attempt)
                        continue
                    raise
                break  # success
            else:
                raise RuntimeError("Spotify rate limit exceeded after max retries")
            
            playlists.extend(data["items"])
            url = data.get("next")
    
    return playlists


async def get_playlist_tracks(
    token: str,
    playlist_ids: list[str],
) -> list[Track]:
    """Fetch every track across the given playlists.

    Handles Spotify's 100-item pagination.  Duplicate tracks (same
    ``spotify_id``) that appear in multiple playlists are deduplicated.
    """
    seen: set[str] = set()
    tracks: list[Track] = []
    cumulative_wait = 0

    async with ClientSession() as session:
        for pid_index, pid in enumerate(playlist_ids, 1):
            url: str | None = (
                f"{SPOTIFY_API}/playlists/{pid}/items"
                "?fields=items(item(id,name,artists(name,id),album(name),duration_ms,linked_from(id))),next"
                "&limit=100&market=US"
            )
            
            while url:
                for attempt in range(_MAX_RETRIES):
                    try:
                        async with session.get(url, headers=_auth_header(token)) as resp:
                            if resp.status == 429:
                                retry_after = int(resp.headers.get("Retry-After", 1))
                                cumulative_wait += retry_after
                                logger.warning(
                                    f"[tracks] Rate limited (429) on playlist {pid_index}. "
                                    f"Waiting {retry_after}s (attempt {attempt + 1}/{_MAX_RETRIES}, cumulative wait: {cumulative_wait}s)"
                                )
                                await asyncio.sleep(retry_after)
                                continue
                            
                            if resp.status == 404:
                                logger.warning(f"[tracks] Playlist {pid} not found (404)")
                                break  # Skip this playlist
                            
                            if resp.status != 200:
                                error_detail = await resp.text()
                                logger.error(
                                    f"[tracks] HTTP {resp.status} error on playlist {pid_index}: {error_detail[:200]}"
                                )
                                resp.raise_for_status()
                            
                            data = await resp.json()
                    except Exception as e:
                        logger.error(f"[tracks] Request failed on playlist {pid_index}: {type(e).__name__}: {e}")
                        if attempt < _MAX_RETRIES - 1:
                            await asyncio.sleep(2 ** attempt)
                            continue
                        raise
                    break
                else:
                    raise RuntimeError("Spotify rate limit exceeded after max retries")

                for item in data.get("items", []):
                    t = item.get("item")
                    if t is None or t.get("id") is None:
                        continue  # local files / unavailable tracks

                    # Prefer the original playlist track ID over a relinked one
                    sid = t.get("linked_from", {}).get("id") or t["id"]
                    if sid in seen:
                        continue
                    seen.add(sid)

                    tracks.append(
                        Track(
                            spotify_id=sid,
                            title=t["name"],
                            artists=[
                                Artist(
                                    name=a["name"],
                                    spotify_id=a.get("id"),
                                )
                                for a in t.get("artists", [])
                            ],
                            album_name=t.get("album", {}).get("name", ""),
                            duration_ms=t.get("duration_ms", 0),
                        )
                    )

                url = data.get("next")

    return tracks

async def create_new_playlist(
    token: str,
    user_id: str,
    name: str,
    description: str = "Created by OffBeat AI"
) -> str:
    """Create a new empty playlist for the user and return its Spotify ID."""
    url = f"{SPOTIFY_API}/users/{user_id}/playlists"
    payload = {
        "name": name,
        "description": description,
        "public": False
    }
    
    async with ClientSession() as session:
        async with session.post(url, headers=_auth_header(token), json=payload) as resp:
            if resp.status not in (200, 201):
                error_detail = await resp.text()
                logger.error(f"[create_playlist] HTTP {resp.status}: {error_detail}")
                resp.raise_for_status()
            
            data = await resp.json()
            return data["id"]


async def add_tracks_to_playlist(
    token: str,
    playlist_id: str,
    track_uris: list[str]
):
    """Add tracks to a playlist, chunking into batches of 100 (Spotify API limit)."""
    url = f"{SPOTIFY_API}/playlists/{playlist_id}/tracks"
    
    async with ClientSession() as session:
        for i in range(0, len(track_uris), 100):
            chunk = track_uris[i:i + 100]
            payload = {"uris": chunk}
            
            async with session.post(url, headers=_auth_header(token), json=payload) as resp:
                if resp.status not in (200, 201):
                    error_detail = await resp.text()
                    logger.error(f"[add_tracks] HTTP {resp.status}: {error_detail}")
                    resp.raise_for_status()
