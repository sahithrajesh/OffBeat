"""Data classes shared across modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Artist:
    name: str
    spotify_id: Optional[str] = None


@dataclass
class Track:
    """Minimal Spotify track info collected from playlists."""

    spotify_id: str
    title: str
    artists: list[Artist]
    album_name: str
    duration_ms: int


@dataclass
class AudioFeatures:
    """Audio features retrieved from ReccoBeats."""

    acousticness: float
    danceability: float
    energy: float
    instrumentalness: float
    liveness: float
    loudness: float
    speechiness: float
    tempo: float
    valence: float
    key: Optional[int] = None
    mode: Optional[int] = None


@dataclass
class Tag:
    """A single Last.fm tag with its weight."""

    name: str
    count: int  # 0-100 relevance weight


@dataclass
class EnrichedTrack:
    """Final fused object combining Spotify metadata, ReccoBeats features, and
    Last.fm tags.  This is the object handed off to later data-processing code.
    """

    spotify_id: str
    title: str
    artists: list[Artist]
    album_name: str
    duration_ms: int
    audio_features: Optional[AudioFeatures] = None
    tags: list[Tag] = field(default_factory=list)

    # ReccoBeats internal id (useful for further API calls)
    reccobeats_id: Optional[str] = None


@dataclass
class Playlist:
    """A Spotify playlist represented as a collection of EnrichedTracks."""

    spotify_id: str
    name: str
    tracks: list[EnrichedTrack] = field(default_factory=list)
    description: Optional[str] = None
    owner: Optional[str] = None
    snapshot_id: Optional[str] = None
    image_url: Optional[str] = None
    total_tracks: int = 0
