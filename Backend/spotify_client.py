"""Spotify Web API helpers – playlist listing and track fetching."""

from __future__ import annotations

from aiohttp import ClientSession

from models import Artist, Track

SPOTIFY_API = "https://api.spotify.com/v1"


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

    async with ClientSession() as session:
        while url:
            async with session.get(url, headers=_auth_header(token)) as resp:
                resp.raise_for_status()
                data = await resp.json()
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

    async with ClientSession() as session:
        for pid in playlist_ids:
            url: str | None = (
                f"{SPOTIFY_API}/playlists/{pid}/items"
                "?fields=items(item(id,name,artists(name,id),album(name),duration_ms,linked_from(id))),next"
                "&limit=100&market=US"
            )
            while url:
                async with session.get(url, headers=_auth_header(token)) as resp:
                    resp.raise_for_status()
                    data = await resp.json()

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
