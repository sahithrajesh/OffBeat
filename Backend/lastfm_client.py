"""Last.fm API client – fetch top tags for tracks."""

from __future__ import annotations

import asyncio
from urllib.parse import quote_plus

from aiohttp import ClientSession

import config
from models import Tag

LASTFM_API = "https://ws.audioscrobbler.com/2.0/"

# Concurrency guard – Last.fm has a soft rate limit.
_CONCURRENCY = 5


async def _fetch_tags_for_track(
    session: ClientSession,
    artist: str,
    track: str,
    semaphore: asyncio.Semaphore,
) -> list[Tag]:
    """Return top tags for a single track."""
    async with semaphore:
        params = {
            "method": "track.getTopTags",
            "artist": artist,
            "track": track,
            "api_key": config.LASTFM_API_KEY,
            "format": "json",
        }
        async with session.get(LASTFM_API, params=params) as resp:
            if resp.status != 200:
                return []
            data = await resp.json()

    tag_list = data.get("toptags", {}).get("tag", [])
    if isinstance(tag_list, dict):
        # When there's only one tag Last.fm may return a dict instead of list
        tag_list = [tag_list]

    return [
        Tag(name=t["name"], count=int(t.get("count", 0)))
        for t in tag_list
        if t.get("name")
    ]


async def fetch_tags(
    tracks: list[tuple[str, str, str]],
) -> dict[str, list[Tag]]:
    """Fetch Last.fm tags for many tracks concurrently.

    Parameters
    ----------
    tracks:
        A list of ``(spotify_id, artist_name, track_title)`` tuples.

    Returns
    -------
    ``{spotify_id: [Tag, …]}``
    """
    sem = asyncio.Semaphore(_CONCURRENCY)
    results: dict[str, list[Tag]] = {}

    async with ClientSession() as session:
        tasks: dict[str, asyncio.Task] = {}
        for spotify_id, artist, title in tracks:
            task = asyncio.create_task(
                _fetch_tags_for_track(session, artist, title, sem)
            )
            tasks[spotify_id] = task

        for spotify_id, task in tasks.items():
            results[spotify_id] = await task

    return results
