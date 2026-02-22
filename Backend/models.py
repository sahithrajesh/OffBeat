"""Data classes shared across modules."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional


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
    """Basic Spotify playlist metadata (without tracks)."""

    spotify_id: str
    name: str
    total_tracks: int
    owner: str
    description: Optional[str] = None
    image_url: Optional[str] = None


@dataclass
class EnrichedPlaylist:
    """A playlist represented as a collection of EnrichedTracks."""

    spotify_id: str
    name: str
    tracks: list[EnrichedTrack] = field(default_factory=list)
    description: Optional[str] = None
    owner: Optional[str] = None
    snapshot_id: Optional[str] = None
    image_url: Optional[str] = None
    total_tracks: int = 0


@dataclass
class AnalysisTrackRow:
    """Per-track analysis result (cluster assignment + anomaly metadata)."""

    spotify_id: str
    title: str
    cluster_id: Optional[int]
    anomaly_score: Optional[float]
    is_anomaly: bool
    reason: str


@dataclass
class AnalysisCentroidFeatures:
    """Cluster centroid summary for audio features and tags."""

    audio_means: Dict[str, Optional[float]] = field(default_factory=dict)
    top_tags: List[str] = field(default_factory=list)
    tag_weights_top: Dict[str, float] = field(default_factory=dict)


@dataclass
class AnalysisCluster:
    """Cluster result with members and centroid summaries."""

    cluster_id: int
    label: str
    size: int
    centroid_features: AnalysisCentroidFeatures
    member_track_ids: List[str] = field(default_factory=list)
    tracks: List[AnalysisTrackRow] = field(default_factory=list)


@dataclass
class AnalysisTrackRef:
    """Minimal track reference for mood index listings."""

    spotify_id: str
    title: Optional[str] = None


@dataclass
class MoodEntry:
    """Mood index entry grouping clusters and tracks by label."""

    mood_label: str
    cluster_ids: List[int] = field(default_factory=list)
    track_ids: List[str] = field(default_factory=list)
    tracks: List[AnalysisTrackRef] = field(default_factory=list)


@dataclass
class AnalysisSummary:
    """Aggregate stats for playlist analysis."""

    num_tracks: int
    num_eligible: int
    num_excluded_missing_all: int
    num_excluded_insufficient_audio_cluster: int
    num_clusters: int
    num_anomalies: int
    anomaly_score_cutoff: Optional[float]
    excluded_track_ids: List[str] = field(default_factory=list)


@dataclass
class AnalysisOutput:
    """Top-level analysis output for a playlist."""

    playlist_id: str
    playlist_name: str
    clusters: List[AnalysisCluster] = field(default_factory=list)
    moods: Dict[str, MoodEntry] = field(default_factory=dict)
    summary: AnalysisSummary | None = None
