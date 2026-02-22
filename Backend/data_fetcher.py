"""Main orchestrator – ties Spotify, ReccoBeats, and Last.fm together.

Public entry point: :func:`run_pipeline`.
"""

from __future__ import annotations

import asyncio
from dataclasses import asdict

from models import EnrichedTrack, Track
from spotify_auth import authenticate
from spotify_client import get_user_playlists, get_playlist_tracks
from reccobeats_client import lookup_reccobeats_ids, fetch_audio_features
from lastfm_client import fetch_tags


def _present_playlists(playlists: list[dict]) -> list[str]:
    """Print playlists and let the user pick one or more by number.

    Returns the selected playlist IDs.
    """
    print("\nYour playlists:\n")
    for i, p in enumerate(playlists, 1):
        total = p.get("tracks", {}).get("total", "?")
        owner = p.get("owner", {}).get("display_name", "")
        print(f"  {i:>3}. {p['name']}  ({total} tracks, by {owner})")

    print(
        "\nEnter playlist numbers separated by commas (e.g. 1,3,5), "
        "or 'all' to select everything:"
    )
    choice = input("> ").strip()

    if choice.lower() == "all":
        return [p["id"] for p in playlists]

    indices = [int(x.strip()) - 1 for x in choice.split(",") if x.strip().isdigit()]
    return [playlists[i]["id"] for i in indices if 0 <= i < len(playlists)]


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


async def run_pipeline() -> list[EnrichedTrack]:
    """Execute the full data-fetching pipeline and return enriched tracks.

    Steps
    -----
    1. Authenticate with Spotify (auth-code flow).
    2. Fetch & display the user's playlists; let them choose.
    3. Fetch all tracks from the selected playlists.
    4A. (concurrent) ReccoBeats: resolve IDs → fetch audio features.
    4B. (concurrent) Last.fm: fetch tags for every track.
    5. Fuse everything into ``EnrichedTrack`` objects.
    """

    # -- Step 1: Authenticate ------------------------------------------------
    print("Starting Spotify authentication…")
    token = await authenticate()
    print("Authenticated successfully.\n")

    # -- Step 2: List playlists ----------------------------------------------
    playlists = await get_user_playlists(token)
    if not playlists:
        print("No playlists found.")
        return []

    selected_ids = _present_playlists(playlists)
    if not selected_ids:
        print("No playlists selected.")
        return []

    # -- Step 3: Fetch tracks ------------------------------------------------
    print(f"\nFetching tracks from {len(selected_ids)} playlist(s)…")
    tracks = await get_playlist_tracks(token, selected_ids)
    print(f"Found {len(tracks)} unique track(s).\n")
    if not tracks:
        return []

    # -- Step 4A & 4B: concurrent ReccoBeats + Last.fm -----------------------
    spotify_ids = [t.spotify_id for t in tracks]

    # Build Last.fm lookup tuples (spotify_id, first artist, title)
    lastfm_tuples = [
        (t.spotify_id, t.artists[0].name if t.artists else "", t.title)
        for t in tracks
    ]

    print("Fetching ReccoBeats features and Last.fm tags concurrently…")

    async def _reccobeats_flow() -> tuple[dict, dict]:
        id_map = await lookup_reccobeats_ids(spotify_ids)
        print(f"  ReccoBeats: resolved {len(id_map)}/{len(spotify_ids)} IDs.")
        features = await fetch_audio_features(id_map)
        print(f"  ReccoBeats: fetched features for {len(features)} track(s).")
        return id_map, features

    async def _lastfm_flow() -> dict:
        tags = await fetch_tags(lastfm_tuples)
        tagged = sum(1 for v in tags.values() if v)
        print(f"  Last.fm: fetched tags for {tagged}/{len(tracks)} track(s).")
        return tags

    (id_mapping, features_map), tags_map = await asyncio.gather(
        _reccobeats_flow(),
        _lastfm_flow(),
    )

    # -- Step 5: Fuse --------------------------------------------------------
    enriched = _fuse(tracks, features_map, tags_map, id_mapping)
    print(f"\nPipeline complete — {len(enriched)} enriched track(s) ready.\n")
    return enriched


# ---- CLI entry point -------------------------------------------------------

def main() -> None:
    results = asyncio.run(run_pipeline())
    with open("enriched_tracks.json", "w", encoding="utf-8") as f:
        import json

        json.dump([asdict(et) for et in results], f, ensure_ascii=False, indent=2)
    print("Enriched track data saved to enriched_tracks.json\n")

    # Quick preview of the first few results
    for et in results[:5]:
        artists = ", ".join(a.name for a in et.artists)
        feat = (
            f"energy={et.audio_features.energy:.2f}, "
            f"valence={et.audio_features.valence:.2f}, "
            f"tempo={et.audio_features.tempo:.0f}"
            if et.audio_features
            else "N/A"
        )
        top_tags = ", ".join(t.name for t in et.tags[:5]) or "none"
        print(f"  {et.title} — {artists}")
        print(f"    features: {feat}")
        print(f"    tags: {top_tags}\n")

    if len(results) > 5:
        print(f"  … and {len(results) - 5} more track(s).")


if __name__ == "__main__":
    main()
