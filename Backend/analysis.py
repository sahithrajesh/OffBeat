"""Playlist analysis module.

Provides clustering, anomaly detection, mood indexing, and playlist
comparison — all operating on ``models.EnrichedPlaylist`` objects so the
server can call these functions directly after enrichment.

Public API
----------
run_playlist_analysis(playlist)    → AnalysisOutput
run_playlists_analysis(playlists)  → dict   (multi-playlist summary)
compare_playlists(playlists)       → dict   (mood-label overlap)
select_tracks_by_mood(playlists, mood_label) → dict
"""

from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler, normalize

import models
from models import (
    AnalysisCentroidFeatures,
    AnalysisCluster,
    AnalysisOutput,
    AnalysisSummary,
    AnalysisTrackRef,
    AnalysisTrackRow,
    EnrichedPlaylist,
    EnrichedTrack,
    MoodEntry,
)

logger = logging.getLogger(__name__)

# ── simple in-memory cache so later actions can reuse results ────────────
_ANALYSIS_CACHE: Dict[str, AnalysisOutput] = {}

AUDIO_FEATURE_COLS = [
    "acousticness",
    "danceability",
    "energy",
    "instrumentalness",
    "liveness",
    "loudness",
    "speechiness",
    "tempo",
    "valence",
]


# ═══════════════════════════════════════════════════════════════════════════
# Feature extraction helpers
# ═══════════════════════════════════════════════════════════════════════════

def _safe_float(x, default: float = np.nan) -> float:
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _extract_audio_features_df(tracks: List[EnrichedTrack]) -> pd.DataFrame:
    """DataFrame indexed by spotify_id with audio-feature columns (may have NaNs)."""
    rows = []
    for t in tracks:
        af = t.audio_features
        row: Dict[str, Any] = {"spotify_id": t.spotify_id}
        if af is None:
            for c in AUDIO_FEATURE_COLS:
                row[c] = np.nan
        else:
            for c in AUDIO_FEATURE_COLS:
                row[c] = _safe_float(getattr(af, c, np.nan))
        rows.append(row)
    return pd.DataFrame(rows).set_index("spotify_id")


def _track_tags_to_text(track: EnrichedTrack) -> str:
    """Weighted-tag string for TF-IDF (replicate proportional to count)."""
    if not track.tags:
        return ""
    toks: list[str] = []
    for tag in track.tags:
        name = (tag.name or "").strip().lower()
        if not name:
            continue
        reps = int(np.clip(round(tag.count / 20), 0, 5))
        toks.extend([name] * max(reps, 1))
    return " ".join(toks)


def _build_tag_tfidf_matrix(
    tracks: List[EnrichedTrack],
    max_features: int = 200,
    min_df: int = 1,
) -> Tuple[pd.DataFrame, TfidfVectorizer]:
    """TF-IDF tag matrix indexed by spotify_id."""
    corpus = [_track_tags_to_text(t) for t in tracks]
    ids = [t.spotify_id for t in tracks]

    if all(len(doc.strip()) == 0 for doc in corpus):
        return pd.DataFrame(index=ids), TfidfVectorizer(max_features=max_features)

    vec = TfidfVectorizer(
        max_features=max_features,
        min_df=min_df,
        token_pattern=r"(?u)\b[^\s]+\b",
    )
    X = vec.fit_transform(corpus)
    df = pd.DataFrame(
        X.toarray(),
        index=ids,
        columns=[f"tag__{t}" for t in vec.get_feature_names_out()],
    )
    return df, vec


def _combine_and_scale_features(
    audio_df: pd.DataFrame,
    tag_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, StandardScaler]:
    """Standardise audio + tag features, then L2-normalise each row."""
    idx = audio_df.index
    tag_df = tag_df.reindex(idx)

    audio_vals = audio_df.values.astype(float)
    scaler = StandardScaler(with_mean=True, with_std=True)

    audio_scaled = np.full_like(audio_vals, np.nan, dtype=float)
    for j in range(audio_vals.shape[1]):
        col = audio_vals[:, j]
        mask = ~np.isnan(col)
        if mask.sum() < 2:
            audio_scaled[:, j] = 0.0
        else:
            c_mean = col[mask].mean()
            c_std = col[mask].std(ddof=0)
            if c_std == 0:
                audio_scaled[:, j] = 0.0
            else:
                audio_scaled[:, j] = np.where(np.isnan(col), 0.0, (col - c_mean) / c_std)

    audio_scaled_df = pd.DataFrame(
        audio_scaled, index=idx, columns=[f"af__{c}" for c in audio_df.columns]
    )

    combined = pd.concat([audio_scaled_df, tag_df.fillna(0.0)], axis=1)
    combined_vals = normalize(combined.values, norm="l2", axis=1)
    combined = pd.DataFrame(combined_vals, index=combined.index, columns=combined.columns)
    return combined, scaler


def _eligible_mask(tracks: List[EnrichedTrack]) -> np.ndarray:
    """True if the track has *any* audio feature OR any tag."""
    return np.array(
        [(t.audio_features is not None or bool(t.tags)) for t in tracks],
        dtype=bool,
    )


# ═══════════════════════════════════════════════════════════════════════════
# Clustering helpers
# ═══════════════════════════════════════════════════════════════════════════

def _choose_k(
    X: np.ndarray,
    k_min: int = 3,
    k_max: int = 8,
    random_state: int = 42,
) -> int:
    """Pick K via silhouette score with safe fallbacks."""
    n = X.shape[0]
    if n <= 2:
        return max(1, n)

    k_min_eff = int(np.clip(k_min, 2, n))
    k_max_eff = int(np.clip(k_max, 2, n))
    if k_min_eff > k_max_eff:
        k_min_eff = k_max_eff

    if n < 3:
        return k_min_eff

    best_k, best_score = k_min_eff, -np.inf
    for k in range(k_min_eff, k_max_eff + 1):
        if k >= n:
            continue
        try:
            km = KMeans(n_clusters=k, n_init=20, random_state=random_state)
            labels = km.fit_predict(X)
            if len(set(labels)) < 2:
                continue
            s = silhouette_score(X, labels)
            if s > best_score:
                best_score = s
                best_k = k
        except Exception:
            continue
    return int(best_k)


def _label_cluster(centroid: pd.Series) -> str:
    """Rule-based cluster label from centroid audio features."""
    energy = centroid.get("energy", np.nan)
    valence = centroid.get("valence", np.nan)
    tempo = centroid.get("tempo", np.nan)

    if pd.notna(energy):
        energy_bucket = (
            "high_energy" if energy >= 0.67 else ("low_energy" if energy <= 0.33 else "medium_energy")
        )
    else:
        energy_bucket = "medium_energy"

    if pd.notna(valence):
        valence_bucket = "happy" if valence >= 0.6 else ("sad" if valence <= 0.4 else "neutral")
    else:
        valence_bucket = "neutral"

    tempo_bucket = ""
    if pd.notna(tempo):
        if tempo >= 130:
            tempo_bucket = "_fast"
        elif tempo <= 90:
            tempo_bucket = "_slow"

    return f"{energy_bucket}_{valence_bucket}{tempo_bucket}".replace("__", "_")


def _compute_centroid_summaries(
    tracks: List[EnrichedTrack],
    cluster_assignments: pd.Series,
    tag_tfidf_df: pd.DataFrame,
    top_n_tags: int = 8,
    max_null_audio_means: int = 2,
) -> List[AnalysisCluster]:
    """Per-cluster centroid summaries in original feature units + top tags."""
    audio_raw_df = _extract_audio_features_df(tracks)
    clusters_out: List[AnalysisCluster] = []

    for cid in sorted(cluster_assignments.dropna().unique().tolist()):
        member_ids = cluster_assignments[cluster_assignments == cid].index.tolist()

        audio_means = audio_raw_df.loc[member_ids].mean(numeric_only=True).to_dict()
        audio_means = {k: (None if pd.isna(v) else float(v)) for k, v in audio_means.items()}

        null_audio_ct = sum(1 for v in audio_means.values() if v is None)
        if null_audio_ct > max_null_audio_means:
            continue  # skip under-specified clusters

        top_tags: List[str] = []
        tag_weights: Dict[str, float] = {}
        if tag_tfidf_df.shape[1] > 0:
            tag_centroid = tag_tfidf_df.loc[member_ids].mean(axis=0)
            top = tag_centroid.sort_values(ascending=False).head(top_n_tags)
            top_tags = [c.replace("tag__", "") for c in top.index.tolist() if top[c] > 0]
            tag_weights = {c.replace("tag__", ""): float(v) for c, v in top.to_dict().items() if v > 0}

        label = _label_cluster(pd.Series(audio_means))

        clusters_out.append(
            AnalysisCluster(
                cluster_id=int(cid),
                label=label,
                size=len(member_ids),
                centroid_features=AnalysisCentroidFeatures(
                    audio_means=audio_means,
                    top_tags=top_tags,
                    tag_weights_top=tag_weights,
                ),
                member_track_ids=member_ids,
            )
        )
    return clusters_out


# ═══════════════════════════════════════════════════════════════════════════
# Core analysis
# ═══════════════════════════════════════════════════════════════════════════

def run_playlist_analysis(
    playlist: EnrichedPlaylist,
    *,
    use_cache: bool = True,
) -> AnalysisOutput:
    """Cluster + anomaly-detect a single playlist.

    Returns a fully-populated ``AnalysisOutput`` dataclass.
    """
    if use_cache and playlist.spotify_id in _ANALYSIS_CACHE:
        return _ANALYSIS_CACHE[playlist.spotify_id]

    tracks = playlist.tracks or []
    eligible = _eligible_mask(tracks)
    eligible_tracks = [t for t, m in zip(tracks, eligible) if m]
    excluded_tracks = [t for t, m in zip(tracks, eligible) if not m]

    # ── empty playlist fast path ────────────────────────────────────────
    if not eligible_tracks:
        out = AnalysisOutput(
            playlist_id=playlist.spotify_id,
            playlist_name=playlist.name,
            summary=AnalysisSummary(
                num_tracks=len(tracks),
                num_eligible=0,
                num_excluded_missing_all=len(excluded_tracks),
                num_excluded_insufficient_audio_cluster=0,
                num_clusters=0,
                num_anomalies=0,
                anomaly_score_cutoff=None,
                excluded_track_ids=[t.spotify_id for t in excluded_tracks],
            ),
        )
        if use_cache:
            _ANALYSIS_CACHE[playlist.spotify_id] = out
        return out

    # ── build feature matrices ──────────────────────────────────────────
    audio_df = _extract_audio_features_df(eligible_tracks)
    tag_df, _ = _build_tag_tfidf_matrix(eligible_tracks, max_features=200, min_df=1)
    X_df, _ = _combine_and_scale_features(audio_df, tag_df)

    X = X_df.values
    n = X.shape[0]

    # ── KMeans clustering ───────────────────────────────────────────────
    if n == 1:
        labels = np.array([0])
        centers = X.copy()
    else:
        k = _choose_k(X, 3, 8)
        k = int(np.clip(k, 1, n))
        if k == 1:
            labels = np.zeros(n, dtype=int)
            centers = np.mean(X, axis=0, keepdims=True)
        else:
            km = KMeans(n_clusters=k, n_init=30, random_state=42)
            labels = km.fit_predict(X)
            centers = km.cluster_centers_

    ids = X_df.index.tolist()
    cluster_series = pd.Series(labels, index=ids, name="cluster_id")

    # ── anomaly scoring (distance to assigned centroid) ─────────────────
    dists = np.linalg.norm(X - centers[labels], axis=1)
    max_dist = np.nanmax(dists)
    anomaly_scores = dists / max_dist if max_dist > 0 else np.zeros_like(dists)

    frac = 0.15
    num_anom = int(np.ceil(frac * n))
    num_anom = max(1, num_anom) if n >= 5 else max(0, min(1, num_anom))

    cutoff: Optional[float] = None
    is_anomaly = np.zeros(n, dtype=bool)
    if num_anom > 0:
        order = np.argsort(-anomaly_scores)
        is_anomaly[order[:num_anom]] = True
        cutoff = float(anomaly_scores[order[num_anom - 1]])

    # ── centroid summaries (drops under-specified clusters) ─────────────
    clusters_out = _compute_centroid_summaries(
        eligible_tracks, cluster_series, tag_df, max_null_audio_means=2
    )
    kept_cluster_ids = {c.cluster_id for c in clusters_out}

    dropped_cluster_track_ids = [
        sid for sid in ids if int(cluster_series.loc[sid]) not in kept_cluster_ids
    ]

    # dominant cluster for anomaly reasoning
    dominant_cluster_id = int(cluster_series.value_counts().idxmax()) if len(cluster_series) else None
    dominant_label: Optional[str] = None
    for c in clusters_out:
        if c.cluster_id == dominant_cluster_id:
            dominant_label = c.label
            break

    # dominant centroid in raw audio space for human-readable reasons
    audio_raw_df_all = _extract_audio_features_df(eligible_tracks)
    dominant_member_ids = [
        tid for tid in cluster_series.index.tolist() if int(cluster_series.loc[tid]) == dominant_cluster_id
    ]
    dominant_audio_centroid = (
        audio_raw_df_all.loc[dominant_member_ids].mean(numeric_only=True) if dominant_member_ids else None
    )

    # ── build per-track rows ────────────────────────────────────────────
    id_to_track = {t.spotify_id: t for t in eligible_tracks}
    track_rows: Dict[str, AnalysisTrackRow] = {}

    for i, sid in enumerate(ids):
        tr = id_to_track[sid]
        assigned_cid = int(cluster_series.loc[sid])

        if assigned_cid not in kept_cluster_ids:
            track_rows[sid] = AnalysisTrackRow(
                spotify_id=sid,
                title=tr.title,
                cluster_id=None,
                anomaly_score=None,
                is_anomaly=False,
                reason="Excluded: assigned cluster has insufficient audio feature coverage",
            )
            continue

        reason = ""
        if is_anomaly[i]:
            pieces = [
                f"Anomalous vs dominant mood '{dominant_label}'" if dominant_label else "Anomalous vs dominant mood"
            ]
            pieces.append(f"distance_score={float(anomaly_scores[i]):.2f}")

            if dominant_audio_centroid is not None and tr.audio_features is not None:
                deltas: Dict[str, float] = {}
                for feat in [
                    "energy", "valence", "tempo", "danceability",
                    "acousticness", "speechiness", "loudness",
                ]:
                    dom_v = dominant_audio_centroid.get(feat, np.nan)
                    tr_v = getattr(tr.audio_features, feat, None)
                    if tr_v is None or pd.isna(dom_v):
                        continue
                    deltas[feat] = float(tr_v) - float(dom_v)

                if deltas:
                    top = sorted(deltas.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
                    human: list[str] = []
                    for feat, dv in top:
                        direction = "higher" if dv > 0 else "lower"
                        if feat == "tempo":
                            human.append(f"{direction} tempo by {abs(dv):.0f} BPM")
                        elif feat == "loudness":
                            human.append(f"{direction} loudness by {abs(dv):.1f} dB")
                        else:
                            human.append(f"{direction} {feat} by {abs(dv):.2f}")
                    pieces.append("; ".join(human))
            elif tr.audio_features is None:
                pieces.append("reason: limited audio features available (mostly tag-driven)")

            reason = ". ".join([p for p in pieces if p]).strip()

        track_rows[sid] = AnalysisTrackRow(
            spotify_id=sid,
            title=tr.title,
            cluster_id=assigned_cid,
            anomaly_score=float(anomaly_scores[i]),
            is_anomaly=bool(is_anomaly[i]),
            reason=reason,
        )

    # excluded tracks (missing both audio + tags)
    for t in excluded_tracks:
        track_rows[t.spotify_id] = AnalysisTrackRow(
            spotify_id=t.spotify_id,
            title=t.title,
            cluster_id=None,
            anomaly_score=None,
            is_anomaly=False,
            reason="Excluded: missing both audio_features and tags",
        )

    # ── attach track rows to clusters ───────────────────────────────────
    for cluster in clusters_out:
        cluster.tracks = [
            track_rows[sid]
            for sid in cluster.member_track_ids
            if sid in track_rows
        ]

    # ── mood index ──────────────────────────────────────────────────────
    moods_index: Dict[str, MoodEntry] = {}
    for c in clusters_out:
        if not c.label:
            continue
        member_ids = [sid for sid in c.member_track_ids if sid not in dropped_cluster_track_ids]
        entry = moods_index.setdefault(
            c.label,
            MoodEntry(mood_label=c.label),
        )
        entry.cluster_ids.append(c.cluster_id)
        entry.track_ids.extend(member_ids)

    for entry in moods_index.values():
        entry.tracks = [
            AnalysisTrackRef(
                spotify_id=sid,
                title=id_to_track[sid].title if sid in id_to_track else None,
            )
            for sid in entry.track_ids
        ]

    # ── assemble output ─────────────────────────────────────────────────
    out = AnalysisOutput(
        playlist_id=playlist.spotify_id,
        playlist_name=playlist.name,
        clusters=clusters_out,
        moods=moods_index,
        summary=AnalysisSummary(
            num_tracks=len(tracks),
            num_eligible=len(eligible_tracks),
            num_excluded_missing_all=len(excluded_tracks),
            num_excluded_insufficient_audio_cluster=len(dropped_cluster_track_ids),
            num_clusters=len(clusters_out),
            num_anomalies=sum(1 for r in track_rows.values() if r.is_anomaly),
            anomaly_score_cutoff=cutoff,
            excluded_track_ids=[t.spotify_id for t in excluded_tracks],
        ),
    )

    if use_cache:
        _ANALYSIS_CACHE[playlist.spotify_id] = out
    return out


def clear_cache(playlist_id: Optional[str] = None) -> None:
    """Clear the analysis cache (all or a single playlist)."""
    if playlist_id:
        _ANALYSIS_CACHE.pop(playlist_id, None)
    else:
        _ANALYSIS_CACHE.clear()


# ═══════════════════════════════════════════════════════════════════════════
# Multi-playlist helpers
# ═══════════════════════════════════════════════════════════════════════════

def run_playlists_analysis(playlists: List[EnrichedPlaylist]) -> List[AnalysisOutput]:
    """Analyse multiple playlists and return the list of ``AnalysisOutput``."""
    return [run_playlist_analysis(pl) for pl in (playlists or [])]


# ═══════════════════════════════════════════════════════════════════════════
# Comparison
# ═══════════════════════════════════════════════════════════════════════════

def _mood_distribution_from_analysis(analysis: AnalysisOutput) -> List[dict]:
    """[{mood_label, proportion}] based on cluster label sizes."""
    label_sizes: Dict[str, int] = {}
    total = 0
    for c in analysis.clusters:
        if not c.label or c.size <= 0:
            continue
        label_sizes[c.label] = label_sizes.get(c.label, 0) + c.size
        total += c.size

    return [
        {"mood_label": label, "proportion": sz / total if total else 0.0}
        for label, sz in sorted(label_sizes.items(), key=lambda kv: kv[1], reverse=True)
    ]


def compare_playlists(
    playlists: List[EnrichedPlaylist],
    top_n: int = 6,
) -> dict:
    """Mood-label-based playlist comparison (requires >= 2 playlists).

    Returns playlists with mood distributions and pairwise overlaps.
    """
    if not playlists or len(playlists) < 2:
        return {
            "error": "compare_playlists requires at least 2 playlists",
            "num_playlists": 0 if not playlists else len(playlists),
            "playlists": [],
            "overlaps": [],
        }

    analyses = {pl.spotify_id: run_playlist_analysis(pl) for pl in playlists}

    playlist_summaries = []
    pid_to_dist: Dict[str, Dict[str, float]] = {}

    for pl in playlists:
        a = analyses[pl.spotify_id]
        dist_list = _mood_distribution_from_analysis(a)
        dist_dict = {d["mood_label"]: float(d["proportion"]) for d in dist_list}
        pid_to_dist[pl.spotify_id] = dist_dict
        playlist_summaries.append({
            "playlist_id": pl.spotify_id,
            "name": pl.name,
            "moods": dist_list[:max(1, int(top_n))] if top_n else dist_list,
        })

    overlaps = []
    for a_pl, b_pl in combinations(playlists, 2):
        da = pid_to_dist.get(a_pl.spotify_id, {})
        db = pid_to_dist.get(b_pl.spotify_id, {})

        top_a = {m["mood_label"] for m in _mood_distribution_from_analysis(analyses[a_pl.spotify_id])[:top_n]}
        top_b = {m["mood_label"] for m in _mood_distribution_from_analysis(analyses[b_pl.spotify_id])[:top_n]}
        shared = sorted(top_a & top_b)

        shared_moods = []
        for label in shared:
            pa = float(da.get(label, 0.0))
            pb = float(db.get(label, 0.0))
            shared_moods.append({
                "mood_label": label,
                "proportion_a": pa,
                "proportion_b": pb,
                "similarity": float(max(0.0, 1.0 - abs(pa - pb))),
            })

        overlaps.append({
            "playlist_id_a": a_pl.spotify_id,
            "playlist_id_b": b_pl.spotify_id,
            "shared_moods": shared_moods,
        })

    return {"playlists": playlist_summaries, "overlaps": overlaps}


# ═══════════════════════════════════════════════════════════════════════════
# Mood selection
# ═══════════════════════════════════════════════════════════════════════════

def select_tracks_by_mood(
    playlists: List[EnrichedPlaylist],
    mood_label: str,
) -> dict:
    """Return tracks across playlists matching a given mood label."""
    if not playlists or not mood_label:
        return {"mood_label": mood_label, "tracks": []}

    out_tracks: List[dict] = []
    for pl in playlists:
        analysis = run_playlist_analysis(pl)
        for c in analysis.clusters:
            if c.label == mood_label:
                for tr in c.tracks:
                    out_tracks.append({
                        "spotify_id": tr.spotify_id,
                        "title": tr.title,
                        "cluster_id": tr.cluster_id,
                        "anomaly_score": tr.anomaly_score,
                        "is_anomaly": tr.is_anomaly,
                        "reason": tr.reason,
                        "playlist_id": pl.spotify_id,
                        "playlist_name": pl.name,
                    })
    return {"mood_label": mood_label, "tracks": out_tracks}


# ═══════════════════════════════════════════════════════════════════════════
# Serialisation helpers (dataclass → dict for JSON responses)
# ═══════════════════════════════════════════════════════════════════════════

def _track_row_to_dict(tr: AnalysisTrackRow) -> dict:
    return {
        "spotify_id": tr.spotify_id,
        "title": tr.title,
        "cluster_id": tr.cluster_id,
        "anomaly_score": tr.anomaly_score,
        "is_anomaly": tr.is_anomaly,
        "reason": tr.reason,
    }


def _cluster_to_dict(c: AnalysisCluster) -> dict:
    return {
        "cluster_id": c.cluster_id,
        "label": c.label,
        "size": c.size,
        "centroid_features": {
            "audio_means": c.centroid_features.audio_means,
            "top_tags": c.centroid_features.top_tags,
            "tag_weights_top": c.centroid_features.tag_weights_top,
        },
        "member_track_ids": c.member_track_ids,
        "tracks": [_track_row_to_dict(tr) for tr in (c.tracks or [])],
    }


def _mood_entry_to_dict(m: MoodEntry) -> dict:
    return {
        "mood_label": m.mood_label,
        "cluster_ids": m.cluster_ids,
        "track_ids": m.track_ids,
        "tracks": [
            {"spotify_id": t.spotify_id, "title": t.title}
            for t in (m.tracks or [])
        ],
    }


def _summary_to_dict(s: AnalysisSummary) -> dict:
    return {
        "num_tracks": s.num_tracks,
        "num_eligible": s.num_eligible,
        "num_excluded_missing_all": s.num_excluded_missing_all,
        "num_excluded_insufficient_audio_cluster": s.num_excluded_insufficient_audio_cluster,
        "num_clusters": s.num_clusters,
        "num_anomalies": s.num_anomalies,
        "anomaly_score_cutoff": s.anomaly_score_cutoff,
        "excluded_track_ids": s.excluded_track_ids,
    }


def analysis_output_to_dict(a: AnalysisOutput) -> dict:
    """Convert an ``AnalysisOutput`` dataclass tree to a JSON-safe dict."""
    return {
        "playlist_id": a.playlist_id,
        "playlist_name": a.playlist_name,
        "clusters": [_cluster_to_dict(c) for c in (a.clusters or [])],
        "moods": {k: _mood_entry_to_dict(v) for k, v in (a.moods or {}).items()},
        "summary": _summary_to_dict(a.summary) if a.summary else None,
    }
