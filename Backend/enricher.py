"""Playlist enrichment – takes Spotify playlist data and returns EnrichedPlaylists.

Public entry point: :func:`enrich_playlists`.
"""

from __future__ import annotations

import asyncio

from models import EnrichedTrack, EnrichedPlaylist, Track
from spotify_client import get_playlist_tracks
from reccobeats_client import lookup_reccobeats_ids, fetch_audio_features
from lastfm_client import fetch_tags


def _fuse(
    tracks: list[Track],
    features_map: dict,
    tags_map: dict,
    id_mapping: dict[str, str],
) -> list[EnrichedTrack]:
    """Merge Spotify track data with ReccoBeats features and Last.fm tags."""
    enriched: list[EnrichedTrack] = []
    for t in tracks:
        enriched.append(
            EnrichedTrack(
                spotify_id=t.spotify_id,
                title=t.title,
                artists=t.artists,
                album_name=t.album_name,
                duration_ms=t.duration_ms,
                audio_features=features_map.get(t.spotify_id),
                tags=tags_map.get(t.spotify_id, []),
                reccobeats_id=id_mapping.get(t.spotify_id),
            )
        )
    return enriched


async def _enrich_tracks(tracks: list[Track]) -> list[EnrichedTrack]:
    """Run the ReccoBeats + Last.fm enrichment pipeline on a list of tracks.

    Fetches audio features and tags concurrently, then fuses them with the
    track metadata.
    """
    if not tracks:
        return []

    spotify_ids = [t.spotify_id for t in tracks]

    # Build Last.fm lookup tuples (spotify_id, first artist, title)
    lastfm_tuples = [
        (t.spotify_id, t.artists[0].name if t.artists else "", t.title)
        for t in tracks
    ]

    print("  Fetching ReccoBeats features and Last.fm tags concurrently…")

    async def _reccobeats_flow() -> tuple[dict, dict]:
        id_map = await lookup_reccobeats_ids(spotify_ids)
        print(f"    ReccoBeats: resolved {len(id_map)}/{len(spotify_ids)} IDs.")
        features = await fetch_audio_features(id_map)
        print(f"    ReccoBeats: fetched features for {len(features)} track(s).")
        return id_map, features

    async def _lastfm_flow() -> dict:
        tags = await fetch_tags(lastfm_tuples)
        tagged = sum(1 for v in tags.values() if v)
        print(f"    Last.fm: fetched tags for {tagged}/{len(tracks)} track(s).")
        return tags

    (id_mapping, features_map), tags_map = await asyncio.gather(
        _reccobeats_flow(),
        _lastfm_flow(),
    )

    return _fuse(tracks, features_map, tags_map, id_mapping)


async def enrich_playlists(
    token: str,
    playlists: list[dict],
) -> list[EnrichedPlaylist]:
    """Enrich one or more Spotify playlists.

    Parameters
    ----------
    token:
        A valid Spotify access token.
    playlists:
        Raw playlist dicts as returned by the Spotify API (must contain at
        least ``id``, ``name``; optional keys: ``description``,
        ``owner.display_name``, ``snapshot_id``, ``images``,
        ``tracks.total``).

    Returns
    -------
    A list of :class:`EnrichedPlaylist` objects, each containing its fully
    enriched tracks.
    """
    enriched_playlists: list[EnrichedPlaylist] = []

    for pl in playlists:
        pid = pl["id"]
        name = pl.get("name", "Unknown")
        print(f"\nEnriching playlist: {name}")

        # Fetch tracks for this single playlist
        tracks = await get_playlist_tracks(token, [pid])
        print(f"  Found {len(tracks)} track(s).")

        # Enrich the tracks
        enriched_tracks = await _enrich_tracks(tracks)

        # Build metadata from the raw playlist dict
        images = pl.get("images") or []
        image_url = images[0]["url"] if images else None

        enriched_playlists.append(
            EnrichedPlaylist(
                spotify_id=pid,
                name=name,
                tracks=enriched_tracks,
                description=pl.get("description"),
                owner=pl.get("owner", {}).get("display_name"),
                snapshot_id=pl.get("snapshot_id"),
                image_url=image_url,
                total_tracks=pl.get("tracks", {}).get("total", len(tracks)),
            )
        )

    total_tracks = sum(len(ep.tracks) for ep in enriched_playlists)
    print(
        f"\nEnrichment complete — {len(enriched_playlists)} playlist(s), "
        f"{total_tracks} enriched track(s) total.\n"
    )
    return enriched_playlists
