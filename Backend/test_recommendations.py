"""Tests for cluster-based ReccoBeats recommendations.

Loads the analysis output from playlist_analysis_insights.json and verifies
that get_cluster_recommendations returns valid, well-structured results
with the expected 5:1 seed-to-recommendation ratio.

Run:
    python test_recommendations.py
"""

from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

# ── Load analysis data ────────────────────────────────────────────────────
DATA_PATH = Path(__file__).parent / "playlist_analysis_insights.json"
assert DATA_PATH.exists(), f"Missing analysis file: {DATA_PATH}"

with DATA_PATH.open() as f:
    ANALYSIS_DATA = json.load(f)

PLAYLISTS = ANALYSIS_DATA["playlists"]

# Pre-compute expected cluster info for assertions
EXPECTED: dict[str, dict] = {}
for pl in PLAYLISTS:
    pid = pl["playlist_id"]
    clusters = {}
    for label, info in pl["clusters"].items():
        non_anomaly_ids = [
            t["spotify_id"]
            for t in info["tracks"]
            if not t.get("is_anomaly", False)
        ]
        clusters[label] = {
            "cluster_id": info["cluster_id"],
            "num_non_anomaly": len(non_anomaly_ids),
            "max_recs": math.ceil(len(non_anomaly_ids) / 5),
            "all_track_ids": {t["spotify_id"] for t in info["tracks"]},
        }
    EXPECTED[pid] = {"playlist_name": pl["playlist_name"], "clusters": clusters}


# ── Helpers ───────────────────────────────────────────────────────────────
PASS = 0
FAIL = 0


def check(condition: bool, msg: str):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  ✓ {msg}")
    else:
        FAIL += 1
        print(f"  ✗ FAIL: {msg}")


# ── Tests ─────────────────────────────────────────────────────────────────
def test_single_playlist():
    """Test recommendations for a single playlist entry."""
    from reccobeats_client import get_cluster_recommendations

    print("\n── test_single_playlist ──")
    pl = PLAYLISTS[0]
    result = asyncio.run(get_cluster_recommendations(pl))

    pid = pl["playlist_id"]
    check(pid in result, f"Result contains playlist ID {pid}")
    check(
        result[pid]["playlist_name"] == pl["playlist_name"],
        f"Playlist name matches: '{pl['playlist_name']}'",
    )

    for label, cdata in result[pid]["clusters"].items():
        exp = EXPECTED[pid]["clusters"][label]
        check(
            cdata["cluster_id"] == exp["cluster_id"],
            f"  [{label}] cluster_id={cdata['cluster_id']}",
        )
        check(
            cdata["num_input_tracks"] == exp["num_non_anomaly"],
            f"  [{label}] num_input_tracks={cdata['num_input_tracks']} (expected {exp['num_non_anomaly']})",
        )
        check(
            cdata["num_recommendations"] > 0,
            f"  [{label}] got {cdata['num_recommendations']} recommendations (> 0)",
        )
        check(
            cdata["num_recommendations"] <= exp["max_recs"],
            f"  [{label}] recs ({cdata['num_recommendations']}) <= max possible ({exp['max_recs']})",
        )


def test_full_analysis():
    """Test recommendations using the full analysis dict (all playlists)."""
    from reccobeats_client import get_cluster_recommendations

    print("\n── test_full_analysis ──")
    result = asyncio.run(get_cluster_recommendations(ANALYSIS_DATA))

    check(len(result) == len(PLAYLISTS), f"Got results for {len(result)} playlists")

    for pid, pdata in result.items():
        check(pid in EXPECTED, f"Playlist {pid} is expected")
        for label, cdata in pdata["clusters"].items():
            check(
                label in EXPECTED[pid]["clusters"],
                f"  [{pdata['playlist_name']}] cluster '{label}' is known",
            )


def test_recommendation_structure():
    """Verify each recommendation has the required fields."""
    from reccobeats_client import get_cluster_recommendations

    print("\n── test_recommendation_structure ──")
    pl = PLAYLISTS[0]
    result = asyncio.run(get_cluster_recommendations(pl))
    pid = pl["playlist_id"]

    required_keys = {"spotify_id", "reccobeats_id", "title", "artists", "duration_ms", "popularity"}

    for label, cdata in result[pid]["clusters"].items():
        for rec in cdata["recommendations"]:
            missing = required_keys - set(rec.keys())
            check(
                len(missing) == 0,
                f"  [{label}] rec '{rec.get('title', '?')}' has all keys (missing={missing or 'none'})",
            )
            check(
                isinstance(rec["spotify_id"], str) and len(rec["spotify_id"]) > 5,
                f"  [{label}] '{rec.get('title', '?')}' has valid spotify_id",
            )
            check(
                isinstance(rec["artists"], list) and len(rec["artists"]) > 0,
                f"  [{label}] '{rec.get('title', '?')}' has ≥ 1 artist",
            )
        # Only check first cluster to keep output manageable
        break


def test_no_duplicate_recommendations_within_cluster():
    """Recs within a cluster should not contain duplicates."""
    from reccobeats_client import get_cluster_recommendations

    print("\n── test_no_duplicate_recommendations_within_cluster ──")
    pl = PLAYLISTS[0]
    result = asyncio.run(get_cluster_recommendations(pl))
    pid = pl["playlist_id"]

    for label, cdata in result[pid]["clusters"].items():
        ids = [r["spotify_id"] for r in cdata["recommendations"]]
        check(
            len(ids) == len(set(ids)),
            f"  [{label}] no duplicate recs ({len(ids)} ids, {len(set(ids))} unique)",
        )


def test_recs_not_in_original_cluster():
    """Recommendations should not include tracks already in the cluster."""
    from reccobeats_client import get_cluster_recommendations

    print("\n── test_recs_not_in_original_cluster ──")
    pl = PLAYLISTS[0]
    result = asyncio.run(get_cluster_recommendations(pl))
    pid = pl["playlist_id"]

    for label, cdata in result[pid]["clusters"].items():
        existing = EXPECTED[pid]["clusters"][label]["all_track_ids"]
        overlap = [r["spotify_id"] for r in cdata["recommendations"] if r["spotify_id"] in existing]
        check(
            len(overlap) == 0,
            f"  [{label}] 0 recs overlap with existing tracks (found {len(overlap)})",
        )


def test_five_to_one_ratio():
    """Verify the 5:1 ratio: ⌈tracks/5⌉ should equal num_recommendations (approx)."""
    from reccobeats_client import get_cluster_recommendations

    print("\n── test_five_to_one_ratio ──")
    pl = PLAYLISTS[0]
    result = asyncio.run(get_cluster_recommendations(pl))
    pid = pl["playlist_id"]

    for label, cdata in result[pid]["clusters"].items():
        expected_calls = math.ceil(cdata["num_input_tracks"] / 5)
        # After dedup some may be removed, so recs <= expected_calls
        check(
            cdata["num_recommendations"] <= expected_calls,
            f"  [{label}] {cdata['num_recommendations']} recs ≤ {expected_calls} (⌈{cdata['num_input_tracks']}/5⌉)",
        )
        # But we should have gotten at least half (barring extreme dedup)
        check(
            cdata["num_recommendations"] >= expected_calls // 2,
            f"  [{label}] {cdata['num_recommendations']} recs ≥ {expected_calls // 2} (at least ~half)",
        )


def test_empty_input():
    """An empty/invalid analysis dict should return an empty result."""
    from reccobeats_client import get_cluster_recommendations

    print("\n── test_empty_input ──")
    result = asyncio.run(get_cluster_recommendations({}))
    check(result == {}, "Empty dict → empty result")

    result = asyncio.run(get_cluster_recommendations({"playlists": []}))
    check(result == {}, "Empty playlists list → empty result")


# ── Runner ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 60)
    print("ReccoBeats Cluster Recommendation Tests")
    print("=" * 60)

    test_empty_input()
    test_single_playlist()
    test_recommendation_structure()
    test_no_duplicate_recommendations_within_cluster()
    test_recs_not_in_original_cluster()
    test_five_to_one_ratio()
    test_full_analysis()

    print("\n" + "=" * 60)
    print(f"Results: {PASS} passed, {FAIL} failed")
    print("=" * 60)
    raise SystemExit(1 if FAIL else 0)
