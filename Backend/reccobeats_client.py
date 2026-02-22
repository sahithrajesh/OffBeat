"""ReccoBeats API client – track lookup and audio-feature retrieval."""

from __future__ import annotations

from aiohttp import ClientSession

from models import AudioFeatures

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