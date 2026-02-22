"""Test script – authenticates with Spotify, lets the user select playlists,
enriches them (using the PocketBase cache), and dumps the result as JSON.

Run directly: ``python data_fetcher.py``
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict

import cache
from models import EnrichedPlaylist
from spotify_auth import authenticate, get_spotify_user
from spotify_client import get_user_playlists
from enricher import enrich_playlists


def _select_playlists(playlists: list[dict]) -> list[dict]:
    """Print playlists and let the user pick one or more by number.

    Returns the selected playlist dicts (not just IDs) so the enricher
    has access to full metadata.
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
        return playlists

    indices = [int(x.strip()) - 1 for x in choice.split(",") if x.strip().isdigit()]
    return [playlists[i] for i in indices if 0 <= i < len(playlists)]


async def run() -> list[EnrichedPlaylist]:
    """Authenticate, select playlists, enrich (cache-aware), and return."""

    # -- Authenticate --------------------------------------------------------
    print("Starting Spotify authentication…")
    token = await authenticate()
    print("Authenticated successfully.\n")

    # Get the current user's Spotify ID for cache keying
    profile = await get_spotify_user(token)
    user_id = profile["id"]
    print(f"Logged in as: {profile.get('display_name', user_id)}\n")

    # -- List & select playlists ---------------------------------------------
    playlists = await get_user_playlists(token)
    if not playlists:
        print("No playlists found.")
        return []

    selected = _select_playlists(playlists)
    if not selected:
        print("No playlists selected.")
        return []

    # -- Enrich with cache ---------------------------------------------------
    cached: list[EnrichedPlaylist] = []
    to_fetch: list[dict] = []

    for pl in selected:
        pid = pl["id"]
        current_snapshot = pl.get("snapshot_id", "")
        cached_snapshot = await cache.get_snapshot_id(user_id, pid)

        if cached_snapshot and cached_snapshot == current_snapshot:
            hit = await cache.get(user_id, pid)
            if hit:
                print(f"  Cache hit: {pl.get('name', pid)} (snapshot unchanged)")
                cached.append(hit)
                continue

        to_fetch.append(pl)

    newly_enriched: list[EnrichedPlaylist] = []
    if to_fetch:
        print(f"\nEnriching {len(to_fetch)} playlist(s) (not cached)…")
        newly_enriched = await enrich_playlists(token, to_fetch)
        for ep in newly_enriched:
            raw = next((p for p in selected if p["id"] == ep.spotify_id), {})
            ep.snapshot_id = raw.get("snapshot_id", "")
            await cache.put(user_id, ep)

    return cached + newly_enriched


# ---- CLI entry point -------------------------------------------------------

def main() -> None:
    results = asyncio.run(run())

    # Dump to JSON
    with open("enriched_playlists.json", "w", encoding="utf-8") as f:
        json.dump([asdict(ep) for ep in results], f, ensure_ascii=False, indent=2)
    print(f"Saved {len(results)} enriched playlist(s) to enriched_playlists.json\n")

    # Quick preview
    for ep in results:
        print(f"  Playlist: {ep.name} ({len(ep.tracks)} tracks)")
        for et in ep.tracks[:3]:
            artists = ", ".join(a.name for a in et.artists)
            feat = (
                f"energy={et.audio_features.energy:.2f}, "
                f"valence={et.audio_features.valence:.2f}, "
                f"tempo={et.audio_features.tempo:.0f}"
                if et.audio_features
                else "N/A"
            )
            top_tags = ", ".join(t.name for t in et.tags[:5]) or "none"
            print(f"    {et.title} — {artists}")
            print(f"      features: {feat}")
            print(f"      tags: {top_tags}")
        if len(ep.tracks) > 3:
            print(f"    … and {len(ep.tracks) - 3} more track(s).")
        print()


if __name__ == "__main__":
    main()
