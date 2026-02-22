"""ReccoBeats API client – track lookup, audio-feature retrieval, and recommendations."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from aiohttp import ClientSession

from models import AudioFeatures

logger = logging.getLogger(__name__)

RECCOBEATS_API = "https://api.reccobeats.com/v1"

# ReccoBeats /track accepts batches of IDs via repeated `ids` params.
# We chunk to avoid overly long query strings.
_BATCH_SIZE = 30

# /audio-features batch endpoint accepts up to 40 IDs per request.
_FEATURES_BATCH_SIZE = 40


async def _lookup_tracks_batch(
    session: ClientSession,
    spotify_ids: list[str],
) -> dict[str, str]:
    """Map Spotify IDs → ReccoBeats UUIDs for one batch.

    Returns a dict ``{spotify_id: reccobeats_id}``.
    """
    params = [("ids", sid) for sid in spotify_ids]
    async with session.get(f"{RECCOBEATS_API}/track", params=params) as resp:
        if resp.status != 200:
            # Some IDs may simply not exist in ReccoBeats – skip quietly.
            return {}
        data = await resp.json()

    mapping: dict[str, str] = {}
    for item in data.get("content", []):
        href: str = item.get("href", "")
        # href looks like "https://open.spotify.com/track/<spotify_id>"
        sid = href.rsplit("/", 1)[-1] if "/track/" in href else None
        if sid and item.get("id"):
            mapping[sid] = item["id"]
    return mapping


async def lookup_reccobeats_ids(
    spotify_ids: list[str],
) -> dict[str, str]:
    """Resolve Spotify IDs to ReccoBeats UUIDs.

    Returns ``{spotify_id: reccobeats_uuid}``.
    """
    mapping: dict[str, str] = {}
    async with ClientSession() as session:
        for i in range(0, len(spotify_ids), _BATCH_SIZE):
            batch = spotify_ids[i : i + _BATCH_SIZE]
            partial = await _lookup_tracks_batch(session, batch)
            mapping.update(partial)
    return mapping


async def _fetch_features_batch(
    session: ClientSession,
    reccobeats_ids: list[str],
    spotify_id_by_rb: dict[str, str],
) -> dict[str, AudioFeatures]:
    """Fetch audio features for a batch of tracks using the batch endpoint.

    Returns ``{spotify_id: AudioFeatures}`` for successfully retrieved tracks.
    """
    params = [("ids", rb_id) for rb_id in reccobeats_ids]
    async with session.get(f"{RECCOBEATS_API}/audio-features", params=params) as resp:
        if resp.status != 200:
            return {}
        data = await resp.json()

    results: dict[str, AudioFeatures] = {}
    for item in data.get("content", []):
        rb_id = item.get("id")
        spotify_id = spotify_id_by_rb.get(rb_id)
        if not spotify_id:
            continue
        results[spotify_id] = AudioFeatures(
            acousticness=item.get("acousticness", 0.0),
            danceability=item.get("danceability", 0.0),
            energy=item.get("energy", 0.0),
            instrumentalness=item.get("instrumentalness", 0.0),
            liveness=item.get("liveness", 0.0),
            loudness=item.get("loudness", 0.0),
            speechiness=item.get("speechiness", 0.0),
            tempo=item.get("tempo", 0.0),
            valence=item.get("valence", 0.0),
            key=item.get("key"),
            mode=item.get("mode"),
        )
    return results


async def fetch_audio_features(
    id_mapping: dict[str, str],
) -> dict[str, AudioFeatures]:
    """Fetch audio features for many tracks using the batch endpoint.

    Parameters
    ----------
    id_mapping:
        ``{spotify_id: reccobeats_uuid}`` as returned by
        :func:`lookup_reccobeats_ids`.

    Returns
    -------
    ``{spotify_id: AudioFeatures}`` for every track whose features were
    successfully retrieved.
    """
    # Build reverse mapping: reccobeats_id → spotify_id
    spotify_id_by_rb = {rb_id: sp_id for sp_id, rb_id in id_mapping.items()}
    rb_ids = list(spotify_id_by_rb.keys())

    results: dict[str, AudioFeatures] = {}

    async with ClientSession() as session:
        for i in range(0, len(rb_ids), _FEATURES_BATCH_SIZE):
            batch = rb_ids[i : i + _FEATURES_BATCH_SIZE]
            partial = await _fetch_features_batch(session, batch, spotify_id_by_rb)
            results.update(partial)

    return results


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

# Max seeds the ReccoBeats /track/recommendation endpoint accepts per call.
_MAX_SEEDS = 5


async def _fetch_recommendations(
    session: ClientSession,
    seeds: list[str],
    size: int = 1,
    audio_params: Optional[dict[str, float]] = None,
) -> list[dict[str, Any]]:
    """Call ``/v1/track/recommendation`` once and return the raw items.

    Parameters
    ----------
    seeds:
        1-5 Spotify (or ReccoBeats) track IDs.
    size:
        How many recommendations to return (1-100).
    audio_params:
        Optional dict of audio-feature filters (e.g. ``{"energy": 0.7}``).
    """
    params: list[tuple[str, str]] = [("size", str(size))]
    for sid in seeds:
        params.append(("seeds", sid))
    if audio_params:
        for key, val in audio_params.items():
            params.append((key, str(val)))

    async with session.get(
        f"{RECCOBEATS_API}/track/recommendation", params=params
    ) as resp:
        if resp.status != 200:
            logger.warning(
                "ReccoBeats /track/recommendation returned %s for seeds=%s",
                resp.status,
                seeds,
            )
            return []
        data = await resp.json()
    return data.get("content", [])


def _parse_recommendation(item: dict[str, Any]) -> dict[str, Any]:
    """Normalise a single recommendation item into a compact dict."""
    href: str = item.get("href", "")
    spotify_id = href.rsplit("/", 1)[-1] if "/track/" in href else None
    artists = [
        {"name": a.get("name", ""), "spotify_id": (a.get("href", "").rsplit("/", 1)[-1] if "/artist/" in a.get("href", "") else None)}
        for a in item.get("artists", [])
    ]
    return {
        "spotify_id": spotify_id,
        "reccobeats_id": item.get("id"),
        "title": item.get("trackTitle", ""),
        "artists": artists,
        "duration_ms": item.get("durationMs"),
        "popularity": item.get("popularity"),
    }


async def get_recommendations_for_seeds(
    seed_ids: list[str],
    size: int = 1,
    audio_params: Optional[dict[str, float]] = None,
) -> list[dict[str, Any]]:
    """Get recommendations for an arbitrary list of seed Spotify IDs.

    Seeds are chunked into groups of ``_MAX_SEEDS`` (5).  For each chunk a
    single call is made requesting ``size`` recommendations.  All results are
    collected and returned.

    With the default ``size=1`` this gives a 5-to-1 ratio: 5 input seeds
    produce 1 recommended track.
    """
    results: list[dict[str, Any]] = []
    async with ClientSession() as session:
        for i in range(0, len(seed_ids), _MAX_SEEDS):
            chunk = seed_ids[i : i + _MAX_SEEDS]
            items = await _fetch_recommendations(
                session, chunk, size=size, audio_params=audio_params,
            )
            for item in items:
                parsed = _parse_recommendation(item)
                if parsed["spotify_id"]:
                    results.append(parsed)
    return results


async def get_cluster_recommendations(
    analysis_data: dict,
    size_per_call: int = 1,
) -> dict[str, Any]:
    """Generate recommendations for every cluster in the analysis output.

    Parameters
    ----------
    analysis_data:
        The full ``playlist_analysis_insights.json`` dict (or a single
        playlist entry from it).
    size_per_call:
        How many recommendations each 5-seed call should return.  The
        default of 1 gives a strict 5-to-1 ratio.

    Returns
    -------
    A dict keyed by playlist ID, containing per-cluster recommendation
    lists::

        {
            "<playlist_id>": {
                "playlist_name": "...",
                "clusters": {
                    "<cluster_label>": {
                        "cluster_id": ...,
                        "num_input_tracks": ...,
                        "recommendations": [ { spotify_id, title, artists, ... }, ... ]
                    },
                    ...
                }
            },
            ...
        }
    """
    # Accept either the top-level insights dict or a single playlist entry.
    if "playlists" in analysis_data:
        playlists = analysis_data["playlists"]
    elif "clusters" in analysis_data:
        playlists = [analysis_data]
    else:
        logger.error("analysis_data has no 'playlists' or 'clusters' key")
        return {}

    output: dict[str, Any] = {}

    for pl in playlists:
        playlist_id = pl.get("playlist_id", "unknown")
        playlist_name = pl.get("playlist_name", "")
        clusters_data = pl.get("clusters", {})

        cluster_results: dict[str, Any] = {}

        for cluster_label, cluster_info in clusters_data.items():
            track_ids = [
                t["spotify_id"]
                for t in cluster_info.get("tracks", [])
                if not t.get("is_anomaly", False)
            ]
            if not track_ids:
                logger.info(
                    "Cluster %s in %s has no non-anomaly tracks, skipping.",
                    cluster_label,
                    playlist_name,
                )
                continue

            # Optional: use the cluster centroid audio features as filters
            centroid = cluster_info.get("centroid_features", {})
            audio_means = centroid.get("audio_means", {})
            audio_params: Optional[dict[str, float]] = None
            if audio_means:
                audio_params = {
                    k: v
                    for k, v in audio_means.items()
                    if k in {
                        "acousticness", "danceability", "energy",
                        "instrumentalness", "liveness", "loudness",
                        "speechiness", "tempo", "valence",
                    }
                }

            logger.info(
                "Cluster '%s' (%d tracks) → %d recommendation calls",
                cluster_label,
                len(track_ids),
                (len(track_ids) + _MAX_SEEDS - 1) // _MAX_SEEDS,
            )

            recs = await get_recommendations_for_seeds(
                track_ids, size=size_per_call, audio_params=audio_params,
            )

            # Deduplicate: don't recommend songs already in the cluster
            existing_ids = {t["spotify_id"] for t in cluster_info.get("tracks", [])}
            seen: set[str] = set()
            deduped: list[dict[str, Any]] = []
            for r in recs:
                sid = r["spotify_id"]
                if sid not in existing_ids and sid not in seen:
                    seen.add(sid)
                    deduped.append(r)
            recs = deduped

            cluster_results[cluster_label] = {
                "cluster_id": cluster_info.get("cluster_id"),
                "num_input_tracks": len(track_ids),
                "num_recommendations": len(recs),
                "recommendations": recs,
            }

        output[playlist_id] = {
            "playlist_name": playlist_name,
            "clusters": cluster_results,
        }

    return output