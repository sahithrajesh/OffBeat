from __future__ import annotations
'''################### BEGIN CELL 1 ###################'''
# Load example_playlists from enriched_playlists.json and inspect missing audio_features/tags
import json
from pathlib import Path
import numpy as np
import pandas as pd

import models

DATA_PATH = Path("enriched_playlists.json")

with DATA_PATH.open("r", encoding="utf-8") as f:
    raw_playlists = json.load(f)

def _artist_from_dict(d: dict) -> models.Artist:
    return models.Artist(name=d["name"], spotify_id=d.get("spotify_id"))

def _audio_features_from_dict(d: dict | None) -> models.AudioFeatures | None:
    if d is None:
        return None
    return models.AudioFeatures(
        acousticness=d["acousticness"],
        danceability=d["danceability"],
        energy=d["energy"],
        instrumentalness=d["instrumentalness"],
        liveness=d["liveness"],
        loudness=d["loudness"],
        speechiness=d["speechiness"],
        tempo=d["tempo"],
        valence=d["valence"],
        key=d.get("key"),
        mode=d.get("mode"),
    )

def _tag_from_dict(d: dict) -> models.Tag:
    return models.Tag(name=d["name"], count=d["count"])

def _enriched_track_from_dict(d: dict) -> models.EnrichedTrack:
    return models.EnrichedTrack(
        spotify_id=d["spotify_id"],
        title=d["title"],
        artists=[_artist_from_dict(a) for a in d.get("artists", [])],
        album_name=d["album_name"],
        duration_ms=d["duration_ms"],
        audio_features=_audio_features_from_dict(d.get("audio_features")),
        tags=[_tag_from_dict(t) for t in d.get("tags", [])],
        reccobeats_id=d.get("reccobeats_id"),
    )

def _enriched_playlist_from_dict(d: dict) -> models.EnrichedPlaylist:
    return models.EnrichedPlaylist(
        spotify_id=d["spotify_id"],
        name=d["name"],
        tracks=[_enriched_track_from_dict(t) for t in d.get("tracks", [])],
        description=d.get("description"),
        owner=d.get("owner"),
        snapshot_id=d.get("snapshot_id"),
        image_url=d.get("image_url"),
        total_tracks=d.get("total_tracks", len(d.get("tracks", []))),
    )

example_playlists: list[models.EnrichedPlaylist] = [_enriched_playlist_from_dict(p) for p in raw_playlists]

print(f"Loaded {len(example_playlists)} playlist(s)")
for pl in example_playlists:
    n = len(pl.tracks)
    has_af = sum(t.audio_features is not None for t in pl.tracks)
    has_tags = sum(len(t.tags) > 0 for t in pl.tracks)
    has_both_missing = sum((t.audio_features is None) and (len(t.tags) == 0) for t in pl.tracks)
    print(f"- {pl.name}: {n} tracks | audio_features: {has_af} | tags: {has_tags} | both missing: {has_both_missing}")

# Peek a couple tracks to sanity-check structure
pl0 = example_playlists[0]
print("\nFirst playlist sample tracks:")
for t in pl0.tracks[:3]:
    print({
        "spotify_id": t.spotify_id,
        "title": t.title,
        "has_audio_features": t.audio_features is not None,
        "num_tags": len(t.tags),
        "top_tags": [tt.name for tt in t.tags[:5]],
    })

'''################### END CELL 1 ###################'''










'''################### BEGIN CELL 2 ###################'''
# Helper utilities for feature extraction, tag encoding, and clustering inputs

from collections import Counter, defaultdict
from typing import Any, Dict, List, Tuple

import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler, normalize
from sklearn.feature_extraction.text import TfidfVectorizer


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


def _safe_float(x, default=np.nan):
    try:
        if x is None:
            return default
        return float(x)
    except Exception:
        return default


def _track_to_row(track: models.EnrichedTrack) -> dict:
    """Flatten EnrichedTrack to a row dict for pandas/JSON outputs."""
    return {
        "spotify_id": track.spotify_id,
        "title": track.title,
        "artists": [a.name for a in (track.artists or [])],
        "album_name": track.album_name,
        "duration_ms": int(track.duration_ms) if track.duration_ms is not None else None,
    }


def _extract_audio_features_df(tracks: List[models.EnrichedTrack]) -> pd.DataFrame:
    """Return DataFrame indexed by spotify_id with audio features (may contain NaNs)."""
    rows = []
    for t in tracks:
        af = t.audio_features
        row = {"spotify_id": t.spotify_id}
        if af is None:
            for c in AUDIO_FEATURE_COLS:
                row[c] = np.nan
        else:
            for c in AUDIO_FEATURE_COLS:
                row[c] = _safe_float(getattr(af, c, np.nan))
        rows.append(row)

    df = pd.DataFrame(rows).set_index("spotify_id")
    return df


def _track_tags_to_text(track: models.EnrichedTrack) -> str:
    """Convert weighted tags into a repeated-token string for TF-IDF.

    We replicate tags proportional to count (0-100). This keeps a simple interface
    with scikit-learn's TfidfVectorizer without custom weighting.
    """
    if not track.tags:
        return ""

    toks = []
    for tag in track.tags:
        name = (tag.name or "").strip().lower()
        if not name:
            continue
        # Mild repetition: 0-100 -> 0-5 copies
        reps = int(np.clip(round(tag.count / 20), 0, 5))
        toks.extend([name] * max(reps, 1))
    return " ".join(toks)


def _build_tag_tfidf_matrix(
    tracks: List[models.EnrichedTrack],
    max_features: int = 200,
    min_df: int = 1,
) -> Tuple[pd.DataFrame, TfidfVectorizer]:
    """TF-IDF tag matrix indexed by spotify_id."""
    corpus = [_track_tags_to_text(t) for t in tracks]
    ids = [t.spotify_id for t in tracks]

    # If all empty, return empty DF
    if all(len(doc.strip()) == 0 for doc in corpus):
        return pd.DataFrame(index=ids), TfidfVectorizer(max_features=max_features)

    vec = TfidfVectorizer(
        max_features=max_features,
        min_df=min_df,
        token_pattern=r"(?u)\b[^\s]+\b",
    )
    X = vec.fit_transform(corpus)
    df = pd.DataFrame(X.toarray(), index=ids, columns=[f"tag__{t}" for t in vec.get_feature_names_out()])
    return df, vec


def _combine_and_scale_features(
    audio_df: pd.DataFrame,
    tag_df: pd.DataFrame,
) -> Tuple[pd.DataFrame, StandardScaler]:
    """Combine audio + tag features with sensible scaling.

    - Audio features are standardized.
    - Tag TF-IDF features are left as-is (already normalized-ish), then we re-normalize
      full vector to unit length to balance audio vs tags.
    """
    # Ensure same index order
    idx = audio_df.index
    tag_df = tag_df.reindex(idx)

    # Standardize audio (ignore all-NaN columns)
    audio_vals = audio_df.values.astype(float)
    scaler = StandardScaler(with_mean=True, with_std=True)

    # StandardScaler can't handle all-NaN columns; replace with 0 after scaling.
    audio_scaled = np.full_like(audio_vals, np.nan, dtype=float)
    for j in range(audio_vals.shape[1]):
        col = audio_vals[:, j]
        mask = ~np.isnan(col)
        if mask.sum() < 2:
            audio_scaled[:, j] = 0.0
        else:
            # fit on non-nan, transform full
            c_mean = col[mask].mean()
            c_std = col[mask].std(ddof=0)
            if c_std == 0:
                audio_scaled[:, j] = 0.0
            else:
                audio_scaled[:, j] = np.where(np.isnan(col), 0.0, (col - c_mean) / c_std)

    audio_scaled_df = pd.DataFrame(audio_scaled, index=idx, columns=[f"af__{c}" for c in audio_df.columns])

    # Combine
    combined = pd.concat([audio_scaled_df, tag_df.fillna(0.0)], axis=1)

    # Unit-normalize each row to balance overall magnitude
    combined_vals = normalize(combined.values, norm="l2", axis=1)
    combined = pd.DataFrame(combined_vals, index=combined.index, columns=combined.columns)
    return combined, scaler


def _eligible_mask(tracks: List[models.EnrichedTrack]) -> np.ndarray:
    """Eligible if has any audio feature OR any tag."""
    mask = []
    for t in tracks:
        has_af = t.audio_features is not None
        has_tags = bool(t.tags)
        mask.append(has_af or has_tags)
    return np.array(mask, dtype=bool)

'''################### END CELL 2 ###################'''










'''################### BEGIN CELL 3 ###################'''
# Implement run_playlist_analysis (clustering + anomaly detection) with robust missing-data handling
from dataclasses import asdict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score


# Simple in-memory cache so later actions can reuse results without re-clustering
_PLAYLIST_ANALYSIS_CACHE: Dict[str, dict] = {}


def _choose_k(X: np.ndarray, k_min: int = 3, k_max: int = 8, random_state: int = 42) -> int:
    """Pick K using silhouette score when possible, otherwise fall back.

    Guards:
    - if n < k_min -> k = max(2, n)
    - silhouette requires k in [2, n-1]
    """
    n = X.shape[0]
    if n <= 2:
        return max(1, n)

    k_min_eff = int(np.clip(k_min, 2, n))
    k_max_eff = int(np.clip(k_max, 2, n))
    if k_min_eff > k_max_eff:
        k_min_eff = k_max_eff

    # If we cannot evaluate silhouette (need at least 3 points for k=2), just choose min.
    if n < 3:
        return k_min_eff

    best_k = k_min_eff
    best_score = -np.inf

    for k in range(k_min_eff, k_max_eff + 1):
        if k >= n:
            continue
        try:
            km = KMeans(n_clusters=k, n_init=20, random_state=random_state)
            labels = km.fit_predict(X)
            # Need at least 2 clusters populated
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
    """Rule-based cluster label using centroid audio features (original scale if available)."""
    # centroid may contain af__ prefixed standardized; but we also compute raw means for interpretability.
    energy = centroid.get("energy", np.nan)
    valence = centroid.get("valence", np.nan)
    tempo = centroid.get("tempo", np.nan)

    # Default buckets
    energy_bucket = "medium_energy"
    if pd.notna(energy):
        if energy >= 0.67:
            energy_bucket = "high_energy"
        elif energy <= 0.33:
            energy_bucket = "low_energy"

    valence_bucket = "neutral"
    if pd.notna(valence):
        if valence >= 0.6:
            valence_bucket = "happy"
        elif valence <= 0.4:
            valence_bucket = "sad"

    tempo_bucket = ""
    if pd.notna(tempo):
        if tempo >= 130:
            tempo_bucket = "_fast"
        elif tempo <= 90:
            tempo_bucket = "_slow"

    return f"{energy_bucket}_{valence_bucket}{tempo_bucket}".replace("__", "_")


def _compute_centroid_summaries(
    tracks: List[models.EnrichedTrack],
    cluster_assignments: pd.Series,
    tag_tfidf_df: pd.DataFrame,
    top_n_tags: int = 8,
    max_null_audio_means: int = 2,
) -> List[dict]:
    """Compute per-cluster centroid summaries in original feature units + top tags."""
    # Raw audio DF (unscaled) for interpretability
    audio_raw_df = _extract_audio_features_df(tracks)

    clusters_out: List[dict] = []
    for cid in sorted(cluster_assignments.dropna().unique().tolist()):
        member_ids = cluster_assignments[cluster_assignments == cid].index.tolist()

        # Mean of raw audio features (skip NaNs)
        audio_means = audio_raw_df.loc[member_ids].mean(numeric_only=True).to_dict()
        audio_means = {k: (None if pd.isna(v) else float(v)) for k, v in audio_means.items()}

        null_audio_ct = sum(1 for v in audio_means.values() if v is None)
        if null_audio_ct > max_null_audio_means:
            # Skip clusters that are too underspecified in audio space (typically tag-only clusters)
            continue

        # Aggregate tags (mean TF-IDF per term)
        tag_means = {}
        top_tags = []
        if tag_tfidf_df.shape[1] > 0:
            tag_centroid = tag_tfidf_df.loc[member_ids].mean(axis=0)
            # Top tags by centroid weight
            top = tag_centroid.sort_values(ascending=False).head(top_n_tags)
            top_tags = [c.replace("tag__", "") for c in top.index.tolist() if top[c] > 0]
            tag_means = {c.replace("tag__", ""): float(v) for c, v in top.to_dict().items() if v > 0}

        label = _label_cluster(pd.Series(audio_means))

        clusters_out.append(
            {
                "cluster_id": int(cid),
                "label": label,
                "size": int(len(member_ids)),
                "centroid_features": {
                    "audio_means": audio_means,
                    "top_tags": top_tags,
                    "tag_weights_top": tag_means,
                },
                "member_track_ids": member_ids,
            }
        )

    return clusters_out


def run_playlist_analysis(playlist: models.EnrichedPlaylist) -> dict:
    """Combined mood clustering + anomaly detection for a single playlist."""
    # Cache
    if playlist.spotify_id in _PLAYLIST_ANALYSIS_CACHE:
        return _PLAYLIST_ANALYSIS_CACHE[playlist.spotify_id]

    tracks = playlist.tracks or []
    eligible = _eligible_mask(tracks)

    eligible_tracks = [t for t, m in zip(tracks, eligible) if m]
    excluded_tracks = [t for t, m in zip(tracks, eligible) if not m]

    # Build feature matrices
    audio_df = _extract_audio_features_df(eligible_tracks)
    tag_df, tag_vec = _build_tag_tfidf_matrix(eligible_tracks, max_features=200, min_df=1)
    X_df, _ = _combine_and_scale_features(audio_df, tag_df)

    # If nothing eligible
    if X_df.shape[0] == 0:
        out = {
            "playlist_id": playlist.spotify_id,
            "playlist_name": playlist.name,
            "clusters": [],
            "tracks": [],
            "summary": {
                "num_tracks": int(len(tracks)),
                "num_eligible": 0,
                "num_excluded_missing_all": int(len(excluded_tracks)),
                "num_clusters": 0,
                "num_anomalies": 0,
                "excluded_track_ids": [t.spotify_id for t in excluded_tracks],
            },
        }
        _PLAYLIST_ANALYSIS_CACHE[playlist.spotify_id] = out
        return out

    X = X_df.values
    n = X.shape[0]

    # Choose K and cluster
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

    # Anomaly score = distance to assigned centroid
    dists = np.linalg.norm(X - centers[labels], axis=1)
    # Normalize 0-1 for API friendliness
    if np.nanmax(dists) > 0:
        anomaly_scores = dists / np.nanmax(dists)
    else:
        anomaly_scores = np.zeros_like(dists)

    # Mark top X% as anomalies (10% default, but at least 1 if n>=5)
    frac = 0.15
    num_anom = int(np.ceil(frac * n))
    if n >= 5:
        num_anom = max(1, num_anom)
    else:
        num_anom = max(0, min(1, num_anom))

    cutoff = None
    is_anomaly = np.zeros(n, dtype=bool)
    if num_anom > 0:
        order = np.argsort(-anomaly_scores)
        is_anomaly[order[:num_anom]] = True
        cutoff = float(anomaly_scores[order[num_anom - 1]])

    # Cluster summaries (drop clusters with too many null audio means)
    clusters_out = _compute_centroid_summaries(eligible_tracks, cluster_series, tag_df, max_null_audio_means=2)

    kept_cluster_ids = {c["cluster_id"] for c in clusters_out}

    # Any tracks assigned to dropped clusters are treated as unclustered/excluded from anomaly logic
    dropped_cluster_track_ids = [sid for sid in ids if int(cluster_series.loc[sid]) not in kept_cluster_ids]

    # Dominant cluster id for anomaly reasons
    dominant_cluster_id = int(cluster_series.value_counts().idxmax()) if len(cluster_series) else None
    dominant_label = None
    for c in clusters_out:
        if c["cluster_id"] == dominant_cluster_id:
            dominant_label = c["label"]
            break

    # Precompute dominant centroid in *raw audio feature space* for more specific anomaly reasons
    audio_raw_df_all = _extract_audio_features_df(eligible_tracks)
    dominant_member_ids = [
        tid for tid in cluster_series.index.tolist() if int(cluster_series.loc[tid]) == dominant_cluster_id
    ]
    dominant_audio_centroid = None
    if dominant_member_ids:
        dom_means = audio_raw_df_all.loc[dominant_member_ids].mean(numeric_only=True)
        # keep only non-null means
        dominant_audio_centroid = dom_means

    # Build per-track analysis rows (eligible + excluded), but DO NOT return a flat `tracks` list.
    # We'll attach full track lists to clusters (under `tracks`, meaning full membership).
    id_to_track = {t.spotify_id: t for t in eligible_tracks}

    track_rows: Dict[str, dict] = {}
    for i, sid in enumerate(ids):
        tr = id_to_track[sid]

        assigned_cid = int(cluster_series.loc[sid])
        if assigned_cid not in kept_cluster_ids:
            track_rows[sid] = {
                "spotify_id": sid,
                "title": tr.title,
                "cluster_id": None,
                "anomaly_score": None,
                "is_anomaly": False,
                "reason": "Excluded: assigned cluster has insufficient audio feature coverage",
            }
            continue

        reason = ""
        if is_anomaly[i]:
            pieces = [f"Anomalous vs dominant mood '{dominant_label}'" if dominant_label else "Anomalous vs dominant mood"]
            pieces.append(f"distance_score={float(anomaly_scores[i]):.2f}")

            if dominant_audio_centroid is not None and tr.audio_features is not None:
                deltas = {}
                for feat in ["energy", "valence", "tempo", "danceability", "acousticness", "speechiness", "loudness"]:
                    dom_v = dominant_audio_centroid.get(feat, np.nan)
                    tr_v = getattr(tr.audio_features, feat, None)
                    if tr_v is None or pd.isna(dom_v):
                        continue
                    deltas[feat] = float(tr_v) - float(dom_v)

                if deltas:
                    top = sorted(deltas.items(), key=lambda kv: abs(kv[1]), reverse=True)[:3]
                    human = []
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

        track_rows[sid] = {
            "spotify_id": sid,
            "title": tr.title,
            "cluster_id": assigned_cid,
            "anomaly_score": float(anomaly_scores[i]),
            "is_anomaly": bool(is_anomaly[i]),
            "reason": reason,
        }

    # Add excluded tracks (missing both audio+tags)
    for t in excluded_tracks:
        track_rows[t.spotify_id] = {
            "spotify_id": t.spotify_id,
            "title": t.title,
            "cluster_id": None,
            "anomaly_score": None,
            "is_anomaly": False,
            "reason": "Excluded: missing both audio_features and tags",
        }

    # Build mood index for later retrieval ("mood finder")
    # mood_label -> {cluster_ids: [...], track_ids: [...], tracks: [...]}
    # NOTE: `tracks` contains ALL tracks for the mood (not just a preview).
    moods_index: Dict[str, dict] = {}
    for c in clusters_out:
        label = c.get("label")
        if not label:
            continue
        member_ids = c.get("member_track_ids", []) or []
        member_ids = [sid for sid in member_ids if sid not in dropped_cluster_track_ids]

        entry = moods_index.setdefault(
            label,
            {
                "mood_label": label,
                "cluster_ids": [],
                "track_ids": [],
                "tracks": [],
            },
        )
        entry["cluster_ids"].append(int(c["cluster_id"]))
        entry["track_ids"].extend(member_ids)

    for label, entry in moods_index.items():
        entry["tracks"] = [
            {"spotify_id": sid, "title": (id_to_track.get(sid).title if id_to_track.get(sid) else None)}
            for sid in entry["track_ids"]
        ]

    # Attach full track lists to clusters under `tracks` (full membership)
    clusters_out_enriched: List[dict] = []
    for c in clusters_out:
        member_ids = c.get("member_track_ids", []) or []
        c2 = dict(c)
        c2["tracks"] = [track_rows[sid] for sid in member_ids if sid in track_rows]
        clusters_out_enriched.append(c2)

    out = {
        "playlist_id": playlist.spotify_id,
        "playlist_name": playlist.name,
        "clusters": clusters_out_enriched,
        "moods": moods_index,
        # NOTE: intentionally omitting a top-level `tracks` list per request
        "summary": {
            "num_tracks": int(len(tracks)),
            "num_eligible": int(len(eligible_tracks)),
            "num_excluded_missing_all": int(len(excluded_tracks)),
            "num_excluded_insufficient_audio_cluster": int(len(dropped_cluster_track_ids)),
            "num_clusters": int(len(clusters_out_enriched)),
            "num_anomalies": int(sum(1 for r in track_rows.values() if r.get("is_anomaly"))),
            "anomaly_score_cutoff": cutoff,
            "excluded_track_ids": [t.spotify_id for t in excluded_tracks],
        },
    }

    _PLAYLIST_ANALYSIS_CACHE[playlist.spotify_id] = out
    return out
'''################### END CELL 3 ###################'''










'''################### BEGIN CELL 4 ###################'''
# Display run_playlist_analysis output (trimmed but structured)
import json

analysis0 = run_playlist_analysis(example_playlists[0])

# Build a readable subset of the payload for notebook display
clusters_preview = []
for c in analysis0.get("clusters", [])[:8]:
    clusters_preview.append(
        {
            "cluster_id": c.get("cluster_id"),
            "label": c.get("label"),
            "size": c.get("size"),
            "centroid_audio_means": (c.get("centroid_features", {}) or {}).get("audio_means", {}),
            "top_tags": (c.get("centroid_features", {}) or {}).get("top_tags", [])[:8],
        }
    )

anomalies = [t for t in analysis0.get("tracks", []) if t.get("is_anomaly")]
excluded = [t for t in analysis0.get("tracks", []) if t.get("cluster_id") is None]

analysis_preview = {
    "playlist_id": analysis0.get("playlist_id"),
    "playlist_name": analysis0.get("playlist_name"),
    "summary": analysis0.get("summary"),
    "clusters_preview": clusters_preview,
    "anomalies_preview": [
        {
            "spotify_id": t.get("spotify_id"),
            "title": t.get("title"),
            "cluster_id": t.get("cluster_id"),
            "anomaly_score": t.get("anomaly_score"),
            "reason": t.get("reason"),
        }
        for t in sorted(anomalies, key=lambda x: x.get("anomaly_score") or -1, reverse=True)[:10]
    ],
    "excluded_preview": [
        {"spotify_id": t.get("spotify_id"), "title": t.get("title"), "reason": t.get("reason")}
        for t in excluded[:10]
    ],
}

print(json.dumps(analysis_preview, indent=2, ensure_ascii=False))
'''################### END CELL 4 ###################'''










'''################### BEGIN CELL 5 ###################'''
# Implement simplified compare_playlists (mood-label distribution + overlap)
from itertools import combinations
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd


def _get_or_run_analysis(pl: models.EnrichedPlaylist) -> dict:
    return run_playlist_analysis(pl)


def _iter_analysis_track_rows(analysis: dict):
    """Yield per-track analysis rows from an analysis dict.

    Supported schemas:
    - Current: analysis['clusters'][*]['tracks']
    - Previous: analysis['clusters'][*]['tracks_preview']
    - Legacy: analysis['tracks']
    """
    if isinstance(analysis.get("clusters"), list):
        for c in analysis.get("clusters") or []:
            for tr in (c.get("tracks") or c.get("tracks_preview") or []):
                yield tr

    for tr in analysis.get("tracks") or []:
        yield tr


def _mood_distribution_from_analysis(analysis: dict) -> List[dict]:
    """Return [{mood_label, proportion}] based on cluster label sizes."""
    clusters = analysis.get("clusters") or []

    label_sizes: Dict[str, int] = {}
    total = 0
    for c in clusters:
        label = c.get("label")
        size = int(c.get("size", 0) or 0)
        if not label or size <= 0:
            continue
        label_sizes[label] = label_sizes.get(label, 0) + size
        total += size

    out = []
    for label, sz in sorted(label_sizes.items(), key=lambda kv: kv[1], reverse=True):
        out.append({"mood_label": label, "proportion": (sz / total if total else 0.0)})
    return out


def run_playlists_analysis(playlists: List[models.EnrichedPlaylist]) -> dict:
    """Run run_playlist_analysis for multiple playlists.

    Returns a compact JSON-serializable bundle suitable for API responses.
    """
    playlists = playlists or []
    out_items = []
    for pl in playlists:
        a = _get_or_run_analysis(pl)
        out_items.append(
            {
                "playlist_id": pl.spotify_id,
                "playlist_name": pl.name,
                "num_clusters": int(len(a.get("clusters") or [])),
                "summary": a.get("summary") or {},
            }
        )

    return {
        "num_playlists": int(len(playlists)),
        "playlists": out_items,
    }


def compare_playlists(playlists: List[models.EnrichedPlaylist], top_n: int = 6) -> dict:
    """Simplified mood-label-based playlist comparison.

    Output:
    - playlists: each playlist's mood distribution over cluster labels
    - overlaps: per pair, shared moods with per-playlist proportions

    Gate: requires >= 2 playlists.
    """
    if playlists is None or len(playlists) < 2:
        return {
            "error": "compare_playlists requires at least 2 playlists",
            "num_playlists": 0 if not playlists else len(playlists),
            "playlists": [],
            "overlaps": [],
        }

    analyses = {pl.spotify_id: _get_or_run_analysis(pl) for pl in playlists}

    playlist_summaries = []
    pid_to_dist: Dict[str, Dict[str, float]] = {}

    for pl in playlists:
        a = analyses[pl.spotify_id]
        dist_list = _mood_distribution_from_analysis(a)
        # keep a dict form for quick overlap lookup
        dist_dict = {d["mood_label"]: float(d["proportion"]) for d in dist_list}
        pid_to_dist[pl.spotify_id] = dist_dict

        # optionally cap to top_n in the payload for UI readability
        dist_list_top = dist_list[: max(1, int(top_n))] if top_n is not None else dist_list
        playlist_summaries.append(
            {
                "playlist_id": pl.spotify_id,
                "name": pl.name,
                "moods": dist_list_top,
            }
        )

    overlaps = []
    for a_pl, b_pl in combinations(playlists, 2):
        da = pid_to_dist.get(a_pl.spotify_id, {})
        db = pid_to_dist.get(b_pl.spotify_id, {})

        # shared moods among the union of both playlists' top_n moods
        top_a = set([m["mood_label"] for m in _mood_distribution_from_analysis(analyses[a_pl.spotify_id])[:top_n]])
        top_b = set([m["mood_label"] for m in _mood_distribution_from_analysis(analyses[b_pl.spotify_id])[:top_n]])
        shared = sorted(list(top_a.intersection(top_b)))

        shared_moods = []
        for label in shared:
            pa = float(da.get(label, 0.0))
            pb = float(db.get(label, 0.0))
            # simple similarity: 1 - absolute difference (bounded [0,1])
            sim = float(max(0.0, 1.0 - abs(pa - pb)))
            shared_moods.append(
                {
                    "mood_label": label,
                    "proportion_a": pa,
                    "proportion_b": pb,
                    "similarity": sim,
                }
            )

        overlaps.append(
            {
                "playlist_id_a": a_pl.spotify_id,
                "playlist_id_b": b_pl.spotify_id,
                "shared_moods": shared_moods,
            }
        )

    return {
        "playlists": playlist_summaries,
        "overlaps": overlaps,
    }


# Keep other functions from earlier cells (select_tracks_by_mood, recommend_for_*).
# They live in other cells and continue to reference run_playlist_analysis.


def select_tracks_by_mood(playlists: List[models.EnrichedPlaylist], mood_label: str) -> dict:
    """Return tracks across playlists matching a given mood label.

    Output schema mirrors other analysis helpers: includes "tracks" list of
    {spotify_id,title,playlist_id,playlist_name,cluster_id,...} rows.
    """
    if not playlists or not mood_label:
        return {"tracks": []}

    out_tracks: List[dict] = []
    for pl in playlists:
        analysis = _get_or_run_analysis(pl)
        # iterate clusters; include tracks whose cluster label matches
        for c in analysis.get("clusters") or []:
            if c.get("label") == mood_label:
                for tr in c.get("tracks") or []:
                    row = dict(tr)
                    row.update({
                        "playlist_id": pl.spotify_id,
                        "playlist_name": pl.name,
                    })
                    out_tracks.append(row)
    return {"mood_label": mood_label, "tracks": out_tracks}


# stub recommendation functions (not exercised in this script)

def recommend_for_anomalies(playlists: List[models.EnrichedPlaylist]) -> dict:
    # placeholder; real logic uses analysis results to build rec payloads
    return {"playlists": []}


def recommend_for_mood(playlists: List[models.EnrichedPlaylist], mood_label: str) -> dict:
    return {"playlists": [], "mood": mood_label}

'''################### END CELL 5 ###################'''










'''################### BEGIN CELL 6 ###################'''
# Fast sanity tests (avoid expensive recommendation passes)
#
# NOTE: Track rows live under analysis['clusters'][*]['tracks'].
# This cell prints only lightweight summaries.

# 1) compare_playlists (requires >=2 playlists)
cp = compare_playlists(example_playlists, top_n=6)
print("compare_playlists:")
if cp.get("error"):
    print("  error:", cp.get("error"))
else:
    print("  num_playlists:", len(cp.get("playlists", [])))
    print("  num_overlap_pairs:", len(cp.get("overlaps", [])))
    if cp.get("overlaps"):
        o = cp["overlaps"][0]
        shared = o.get("shared_moods", []) or []
        print("  shared moods (first pair, up to 5):")
        for sm in shared[:5]:
            print(
                f"    - {sm['mood_label']}: {sm.get('proportion_a', 0.0):.1%} vs {sm.get('proportion_b', 0.0):.1%}"
            )

# 2) run_playlist_analysis summary (cached) + pick a mood and test select_tracks_by_mood

a0 = run_playlist_analysis(example_playlists[0])
print("\nrun_playlist_analysis (playlist 0):")
print("  playlist:", a0.get("playlist_name"))
print("  summary:", a0.get("summary"))

moods = list((a0.get("moods") or {}).keys())
if moods:
    mood_label = moods[0]
    sel = select_tracks_by_mood(example_playlists, mood_label)
    print("\nselect_tracks_by_mood:")
    print("  mood_label:", mood_label)
    print("  num_tracks:", len(sel.get("tracks", []) or []))
    if sel.get("tracks"):
        print("  sample:", sel["tracks"][0])
else:
    print("\nselect_tracks_by_mood: no moods available in analysis")

# NOTE: intentionally skipping recommend_for_anomalies / recommend_for_mood here,
# because they can be expensive (nearest-neighbor style scans across many tracks).
'''################### END CELL 6 ###################'''










'''################### BEGIN CELL 7 ###################'''
# Write analysis insights payload for ALL playlists in enriched_playlists.json
# IMPORTANT:
# - Write ONLY to playlist_analysis_insights.json
# - Include per-cluster songs nested under cluster label (for mood/cluster retrieval)
# - Also include anomalies list for lightweight anomaly views

from pathlib import Path
import json

OUT_PATH = Path("playlist_analysis_insights.json")

# Clear cache (safe if analysis code changed recently)
try:
    _PLAYLIST_ANALYSIS_CACHE.clear()
except Exception:
    pass

per_playlist = []
for pl in (example_playlists or []):
    analysis = run_playlist_analysis(pl)

    # Build cluster-label -> tracks mapping from analysis clusters
    clusters_by_label = {}
    for c in (analysis.get("clusters") or []):
        label = c.get("label")
        if not label:
            continue

        clusters_by_label[label] = {
            "cluster_id": c.get("cluster_id"),
            "size": c.get("size"),
            "centroid_features": c.get("centroid_features"),
            # Full track dicts live under cluster['tracks']
            "tracks": c.get("tracks") or [],
        }

    # Collect anomalies from cluster-nested tracks
    anomalies = []
    for label, cinfo in clusters_by_label.items():
        for tr in (cinfo.get("tracks") or []):
            if tr.get("is_anomaly"):
                anomalies.append(tr)

    anomalies_sorted = sorted(anomalies, key=lambda x: x.get("anomaly_score") or -1, reverse=True)

    per_playlist.append(
        {
            "playlist_id": analysis.get("playlist_id"),
            "playlist_name": analysis.get("playlist_name"),
            "summary": analysis.get("summary"),
            # Key requirement: cluster label -> all songs in that cluster
            "clusters": clusters_by_label,
            # Convenience: anomalies only
            "anomalies": [
                {
                    "spotify_id": t.get("spotify_id"),
                    "title": t.get("title"),
                    "cluster_id": t.get("cluster_id"),
                    "anomaly_score": t.get("anomaly_score"),
                    "reason": t.get("reason"),
                }
                for t in anomalies_sorted
            ],
        }
    )

insights_payload = {
    "generated_at": pd.Timestamp.utcnow().isoformat(),
    "num_playlists": len(per_playlist),
    "playlists": per_playlist,
}

OUT_PATH.write_text(json.dumps(insights_payload, indent=2, ensure_ascii=False), encoding="utf-8")

print(f"Wrote multi-playlist analysis insights to: {OUT_PATH.resolve()}")
print("Playlists written:", len(per_playlist))
for p in per_playlist:
    n_clusters = len(p.get("clusters") or {})
    n_cluster_songs = sum(len(v.get("tracks") or []) for v in (p.get("clusters") or {}).values())
    print(f"- {p['playlist_name']}: clusters={n_clusters} clustered_songs={n_cluster_songs} anomalies={len(p['anomalies'])}")
'''################### END CELL 7 ###################'''










'''################### BEGIN CELL 8 ###################'''
# Test multi-playlist analysis wrapper + compare_playlists gate

# Build a 2-playlist list by duplicating the same example playlist with a new id/name
pl_a = example_playlists[0]
pl_b = models.EnrichedPlaylist(
    spotify_id=pl_a.spotify_id + "_copy",
    name=pl_a.name + " (Copy)",
    tracks=pl_a.tracks,
    description=getattr(pl_a, "description", None),
    owner=getattr(pl_a, "owner", None),
    snapshot_id=getattr(pl_a, "snapshot_id", None),
    image_url=getattr(pl_a, "image_url", None),
    total_tracks=getattr(pl_a, "total_tracks", len(pl_a.tracks)),
)

multi = run_playlists_analysis([pl_a, pl_b])
print("run_playlists_analysis:")
print("  num_playlists:", multi.get("num_playlists"))
print("  per-playlist summaries:")
for item in multi.get("playlists", [])[:5]:
    summ = item.get("summary") or {}
    print(
        "   -",
        item.get("playlist_name"),
        "clusters=",
        item.get("num_clusters"),
        "num_tracks=",
        summ.get("num_tracks"),
        "num_eligible=",
        summ.get("num_eligible"),
    )

print("\ncompare_playlists gate tests:")
cp1 = compare_playlists([pl_a])
print("  1 playlist -> has error?", "error" in cp1, "|", cp1.get("error"))
cp2 = compare_playlists([pl_a, pl_b])
# compare_playlists now returns overlaps (mood-label based), not similarities
print("  2 playlists -> num_overlap_pairs:", len(cp2.get("overlaps", [])))
if cp2.get("overlaps"):
    print("   sample overlap:", cp2["overlaps"][0])
'''################### END CELL 8 ###################'''










'''################### BEGIN CELL 9 ###################'''
# Clear cached analyses and regenerate to ensure the new `moods` mapping is present

# Invalidate cache for current example playlists
try:
    _PLAYLIST_ANALYSIS_CACHE.clear()
except NameError:
    pass

analysis0 = run_playlist_analysis(example_playlists[0])

# Quick check that moods -> songs mapping exists and is populated
moods = analysis0.get("moods", {}) or {}
print("moods mapping present?", bool(moods))
print("num moods:", len(moods))
for k in list(moods.keys())[:10]:
    v = moods[k]
    print(f"- {k}: clusters={len(v.get('cluster_ids', []))} tracks={len(v.get('track_ids', []))}")

# Rewrite insights file so backend/UI can load moods quickly
from pathlib import Path
import json

insights_payload = {
    "generated_at": pd.Timestamp.utcnow().isoformat(),
    "analysis_preview": {
        "playlist_id": analysis0.get("playlist_id"),
        "playlist_name": analysis0.get("playlist_name"),
        "summary": analysis0.get("summary"),
        "moods_preview": {
            k: {
                "num_tracks": len(v.get("track_ids", []) or []),
                "tracks_preview": v.get("tracks_preview", [])[:5],
            }
            for k, v in list(moods.items())[:10]
        },
    },
    "analysis_full": analysis0,
}

OUT_PATH = Path("playlist_analysis_insights.json")
OUT_PATH.write_text(json.dumps(insights_payload, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Wrote updated insights (with moods) to: {OUT_PATH.resolve()}")
'''################### END CELL 9 ###################'''










'''################### BEGIN CELL 10 ###################'''
# Test simplified compare_playlists with a concise shared-moods summary
cp = compare_playlists(example_playlists, top_n=6)

print("compare_playlists (simplified):")
print("  playlists returned:", len(cp.get("playlists", [])))
print("  overlap pairs:", len(cp.get("overlaps", [])))

# Print a concise shared-moods summary for the first pair (expected: 2 playlists -> 1 pair)
if cp.get("overlaps"):
    o = cp["overlaps"][0]
    pid_a, pid_b = o.get("playlist_id_a"), o.get("playlist_id_b")
    name_a = next((p["name"] for p in cp.get("playlists", []) if p["playlist_id"] == pid_a), pid_a)
    name_b = next((p["name"] for p in cp.get("playlists", []) if p["playlist_id"] == pid_b), pid_b)

    shared = o.get("shared_moods", []) or []
    print(f"\nShared moods between '{name_a}' and '{name_b}' (top overlap):")
    if not shared:
        print("  (no shared moods in top-N)")
    else:
        for sm in shared:
            print(
                f"  - {sm['mood_label']}: "
                f"{sm['proportion_a']:.1%} vs {sm['proportion_b']:.1%} "
                f"(similarity={sm.get('similarity', 0.0):.2f})"
            )
else:
    print("\nNo overlaps computed (need >=2 playlists).")
'''################### END CELL 10 ###################'''










'''################### BEGIN CELL 11 ###################'''
# End-to-end test: confirm insights includes ALL playlists
from pathlib import Path
import json

print("len(example_playlists):", len(example_playlists))

# Re-run the insights writer by calling its logic: just execute cell 7 before running this cell.
# Here we only validate the written file.
insights_path = Path("playlist_analysis_insights.json")
assert insights_path.exists(), f"Missing insights file: {insights_path.resolve()}"

payload = json.loads(insights_path.read_text(encoding="utf-8"))
pls = payload.get("playlists") or []
print("insights num_playlists field:", payload.get("num_playlists"))
print("insights playlists entries:", len(pls))

for i, p in enumerate(pls):
    print(
        f"- [{i}] {p.get('playlist_name')} ({p.get('playlist_id')}) | "
        f"clusters={len(p.get('clusters') or {})} | anomalies={len(p.get('anomalies') or [])}"
    )

# Hard check: should match input playlists count
if len(pls) != len(example_playlists):
    raise AssertionError(
        f"Insights file contains {len(pls)} playlist entries but example_playlists has {len(example_playlists)}"
    )
'''################### END CELL 11 ###################'''