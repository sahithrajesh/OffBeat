"""Persistent cache backed by PocketBase with normalised storage.

Two collections are used:

1. **enriched_tracks** – one record per *globally unique* Spotify track.
   Shared across all users/playlists.  A track that appears in 10 playlists
   is stored (and enriched) exactly once.

2. **enriched_playlists** – per-user playlist metadata + an ordered list of
   track Spotify IDs.  The actual track data is resolved by joining against
   ``enriched_tracks`` at read time.

PocketBase collection setup
----------------------------

**enriched_tracks** (Base collection):

    spotify_id       (text, unique)  – Spotify track ID (the primary key)
    title            (text)
    artists          (json)          – [{name, spotify_id}, ...]
    album_name       (text)
    duration_ms      (number)
    audio_features   (json)          – nullable
    tags             (json)          – [{name, count}, ...]
    reccobeats_id    (text)          – nullable

    → Add a **unique index** on ``spotify_id``.

**enriched_playlists** (Base collection):

    user_id          (text)          – Spotify user ID
    playlist_id      (text)          – Spotify playlist ID
    snapshot_id      (text)          – Used for cache invalidation
    name             (text)
    description      (text)          – optional
    owner            (text)          – optional
    image_url        (text)          – optional
    total_tracks     (number)
    track_ids        (json)          – Ordered list of Spotify track IDs

    → Add a **unique index** on (``user_id``, ``playlist_id``).
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict
from typing import Any, Optional

from pocketbase.utils import ClientResponseError

from models import (
    Artist,
    AudioFeatures,
    EnrichedPlaylist,
    EnrichedTrack,
    Tag,
)

logger = logging.getLogger(__name__)

_TRACKS_COLLECTION = "enriched_tracks"
_PLAYLISTS_COLLECTION = "enriched_playlists"


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------

def _track_to_payload(t: EnrichedTrack) -> dict[str, Any]:
    """Convert an EnrichedTrack to a PocketBase-ready dict."""
    return {
        "spotify_id": t.spotify_id,
        "title": t.title,
        "artists": json.dumps([asdict(a) for a in t.artists], ensure_ascii=False),
        "album_name": t.album_name,
        "duration_ms": t.duration_ms,
        "audio_features": json.dumps(asdict(t.audio_features), ensure_ascii=False) if t.audio_features else "",
        "tags": json.dumps([asdict(tg) for tg in t.tags], ensure_ascii=False),
        "reccobeats_id": t.reccobeats_id or "",
    }


def _record_to_track(rec: Any) -> EnrichedTrack:
    """Reconstruct an EnrichedTrack from a PocketBase record."""
    artists_raw = getattr(rec, "artists", "[]")
    if isinstance(artists_raw, str):
        artists_raw = json.loads(artists_raw) if artists_raw else []
    artists = [Artist(**a) for a in artists_raw]

    af_raw = getattr(rec, "audio_features", None)
    if isinstance(af_raw, str):
        af_raw = json.loads(af_raw) if af_raw else None
    audio_features = AudioFeatures(**af_raw) if af_raw else None

    tags_raw = getattr(rec, "tags", "[]")
    if isinstance(tags_raw, str):
        tags_raw = json.loads(tags_raw) if tags_raw else []
    tags = [Tag(**tg) for tg in tags_raw]

    return EnrichedTrack(
        spotify_id=getattr(rec, "spotify_id", ""),
        title=getattr(rec, "title", ""),
        artists=artists,
        album_name=getattr(rec, "album_name", ""),
        duration_ms=getattr(rec, "duration_ms", 0),
        audio_features=audio_features,
        tags=tags,
        reccobeats_id=getattr(rec, "reccobeats_id", None) or None,
    )


# ---------------------------------------------------------------------------
# Low-level sync helpers (run inside asyncio.to_thread)
# ---------------------------------------------------------------------------

def _get_client():
    from pocketbase_client import _client, _ensure_admin_auth
    _ensure_admin_auth()
    return _client


# ---- Track CRUD -----------------------------------------------------------

def _find_tracks_sync(spotify_ids: list[str]) -> dict[str, EnrichedTrack]:
    """Return a mapping {spotify_id: EnrichedTrack} for IDs that exist."""
    if not spotify_ids:
        return {}
    client = _get_client()
    found: dict[str, EnrichedTrack] = {}
    # PocketBase filter OR chains; batch in groups to stay under URL limits
    batch_size = 50
    for i in range(0, len(spotify_ids), batch_size):
        batch = spotify_ids[i : i + batch_size]
        filter_parts = " || ".join(f'spotify_id="{sid}"' for sid in batch)
        try:
            page = 1
            while True:
                result = client.collection(_TRACKS_COLLECTION).get_list(
                    page, 100, {"filter": filter_parts}
                )
                for rec in result.items:
                    track = _record_to_track(rec)
                    found[track.spotify_id] = track
                if len(result.items) < 100:
                    break
                page += 1
        except ClientResponseError as exc:
            logger.warning(f"Track lookup batch failed: {exc}")
    return found


def _upsert_track_sync(track: EnrichedTrack) -> None:
    """Create or update a single enriched track record."""
    client = _get_client()
    payload = _track_to_payload(track)
    try:
        result = client.collection(_TRACKS_COLLECTION).get_list(
            1, 1, {"filter": f'spotify_id="{track.spotify_id}"'}
        )
        if result.items:
            client.collection(_TRACKS_COLLECTION).update(result.items[0].id, payload)
        else:
            client.collection(_TRACKS_COLLECTION).create(payload)
    except ClientResponseError as exc:
        logger.error(f"Failed to upsert track {track.spotify_id}: {exc}")


def _upsert_tracks_sync(tracks: list[EnrichedTrack]) -> None:
    """Persist enriched tracks, skipping any that already exist in the DB.

    Enriched data for a given spotify_id never changes, so we only need
    to INSERT new tracks — no updates required.  This reduces N individual
    GET+PATCH round-trips to one batch lookup + only the truly new INSERTs.
    """
    if not tracks:
        return

    client = _get_client()
    all_sids = [t.spotify_id for t in tracks]

    # Batch-check which tracks already exist (reuse the efficient OR-filter lookup)
    existing = _find_tracks_sync(all_sids)
    new_tracks = [t for t in tracks if t.spotify_id not in existing]

    if not new_tracks:
        logger.info(f"All {len(tracks)} tracks already cached, skipping writes.")
        return

    logger.info(f"Inserting {len(new_tracks)} new tracks ({len(existing)} already cached).")
    for t in new_tracks:
        payload = _track_to_payload(t)
        try:
            client.collection(_TRACKS_COLLECTION).create(payload)
        except ClientResponseError as exc:
            # Could be a race condition duplicate — safe to ignore
            logger.debug(f"Track {t.spotify_id} create failed (likely dup): {exc}")


# ---- Playlist CRUD --------------------------------------------------------

def _find_playlist_sync(user_id: str, playlist_id: str) -> Optional[dict[str, Any]]:
    client = _get_client()
    try:
        result = client.collection(_PLAYLISTS_COLLECTION).get_list(
            1, 1,
            {"filter": f'user_id="{user_id}" && playlist_id="{playlist_id}"'},
        )
        if result.items:
            rec = result.items[0]
            track_ids_raw = getattr(rec, "track_ids", "[]")
            if isinstance(track_ids_raw, str):
                track_ids_raw = json.loads(track_ids_raw) if track_ids_raw else []
            return {
                "id": rec.id,
                "user_id": getattr(rec, "user_id", None),
                "playlist_id": getattr(rec, "playlist_id", None),
                "snapshot_id": getattr(rec, "snapshot_id", None),
                "name": getattr(rec, "name", None),
                "description": getattr(rec, "description", None),
                "owner": getattr(rec, "owner", None),
                "image_url": getattr(rec, "image_url", None),
                "total_tracks": getattr(rec, "total_tracks", 0),
                "track_ids": track_ids_raw,
            }
        return None
    except ClientResponseError:
        return None


def _upsert_playlist_sync(user_id: str, ep: EnrichedPlaylist) -> None:
    client = _get_client()
    track_ids = [t.spotify_id for t in ep.tracks]
    payload = {
        "user_id": user_id,
        "playlist_id": ep.spotify_id,
        "snapshot_id": ep.snapshot_id or "",
        "name": ep.name,
        "description": ep.description or "",
        "owner": ep.owner or "",
        "image_url": ep.image_url or "",
        "total_tracks": ep.total_tracks or len(ep.tracks),
        "track_ids": json.dumps(track_ids),
    }
    existing = _find_playlist_sync(user_id, ep.spotify_id)
    if existing:
        client.collection(_PLAYLISTS_COLLECTION).update(existing["id"], payload)
    else:
        client.collection(_PLAYLISTS_COLLECTION).create(payload)


def _get_all_playlists_sync(user_id: str) -> list[dict[str, Any]]:
    client = _get_client()
    records: list[dict[str, Any]] = []
    try:
        page = 1
        while True:
            result = client.collection(_PLAYLISTS_COLLECTION).get_list(
                page, 50, {"filter": f'user_id="{user_id}"'}
            )
            for rec in result.items:
                track_ids_raw = getattr(rec, "track_ids", "[]")
                if isinstance(track_ids_raw, str):
                    track_ids_raw = json.loads(track_ids_raw) if track_ids_raw else []
                records.append({
                    "id": rec.id,
                    "user_id": getattr(rec, "user_id", None),
                    "playlist_id": getattr(rec, "playlist_id", None),
                    "snapshot_id": getattr(rec, "snapshot_id", None),
                    "name": getattr(rec, "name", None),
                    "description": getattr(rec, "description", None),
                    "owner": getattr(rec, "owner", None),
                    "image_url": getattr(rec, "image_url", None),
                    "total_tracks": getattr(rec, "total_tracks", 0),
                    "track_ids": track_ids_raw,
                })
            if len(result.items) < 50:
                break
            page += 1
    except ClientResponseError:
        pass
    return records


def _delete_sync(record_id: str) -> None:
    client = _get_client()
    try:
        client.collection(_PLAYLISTS_COLLECTION).delete(record_id)
    except ClientResponseError:
        pass


def _resolve_playlist_sync(record: dict[str, Any]) -> EnrichedPlaylist:
    """Given a playlist record (with track_ids), resolve full tracks."""
    track_ids: list[str] = record.get("track_ids", [])
    tracks_map = _find_tracks_sync(track_ids)
    # Preserve order
    ordered_tracks = [tracks_map[sid] for sid in track_ids if sid in tracks_map]
    return EnrichedPlaylist(
        spotify_id=record["playlist_id"],
        name=record.get("name", ""),
        tracks=ordered_tracks,
        description=record.get("description"),
        owner=record.get("owner"),
        snapshot_id=record.get("snapshot_id"),
        image_url=record.get("image_url"),
        total_tracks=record.get("total_tracks", len(ordered_tracks)),
    )


# ---------------------------------------------------------------------------
# Async public API
# ---------------------------------------------------------------------------

async def get_cached_tracks(spotify_ids: list[str]) -> dict[str, EnrichedTrack]:
    """Return already-cached EnrichedTracks keyed by spotify_id.

    This is the key function that prevents redundant API calls — the
    enricher calls this first, then only enriches the missing ones.
    """
    return await asyncio.to_thread(_find_tracks_sync, spotify_ids)


async def save_tracks(tracks: list[EnrichedTrack]) -> None:
    """Persist enriched tracks to PocketBase (upsert)."""
    if tracks:
        await asyncio.to_thread(_upsert_tracks_sync, tracks)


async def get_snapshot_id(user_id: str, playlist_id: str) -> Optional[str]:
    """Return the cached snapshot_id for a playlist, or None."""
    record = await asyncio.to_thread(_find_playlist_sync, user_id, playlist_id)
    if record is None:
        return None
    return record.get("snapshot_id")


async def get(user_id: str, playlist_id: str) -> Optional[EnrichedPlaylist]:
    """Return a fully-resolved EnrichedPlaylist from the cache, or None."""
    record = await asyncio.to_thread(_find_playlist_sync, user_id, playlist_id)
    if record is None:
        return None
    try:
        return await asyncio.to_thread(_resolve_playlist_sync, record)
    except Exception as exc:
        logger.warning(f"Failed to resolve cached playlist {playlist_id}: {exc}")
        return None


async def put(user_id: str, playlist: EnrichedPlaylist) -> None:
    """Save enriched tracks + playlist reference to PocketBase."""
    # 1. Upsert all tracks
    await save_tracks(playlist.tracks)
    # 2. Upsert playlist metadata + track_ids
    await asyncio.to_thread(_upsert_playlist_sync, user_id, playlist)


async def get_all(user_id: str) -> list[EnrichedPlaylist]:
    """Return all cached EnrichedPlaylists for a user (fully resolved)."""
    records = await asyncio.to_thread(_get_all_playlists_sync, user_id)
    playlists: list[EnrichedPlaylist] = []
    for rec in records:
        try:
            ep = await asyncio.to_thread(_resolve_playlist_sync, rec)
            playlists.append(ep)
        except Exception as exc:
            logger.warning(f"Skipping corrupt cache record: {exc}")
    return playlists


async def clear(user_id: str) -> None:
    """Remove all cached playlist records for a user.

    Note: shared track records are intentionally kept — they may be
    referenced by other users' playlists.
    """
    records = await asyncio.to_thread(_get_all_playlists_sync, user_id)
    for rec in records:
        await asyncio.to_thread(_delete_sync, rec["id"])
