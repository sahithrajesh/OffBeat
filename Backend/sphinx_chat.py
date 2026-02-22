"""Sphinx CLI integration for the OffBeat chatbot.

Provides a per-user notebook lifecycle:
  1. Seed a new notebook with the user's current analysis data.
  2. Run ``sphinx-cli chat`` on the notebook with the user's prompt.
  3. Parse newly-created cells from the notebook for text + images.

The module keeps one notebook per (user, session) pair under
``_sphinx_sessions/`` so follow-up questions carry context via Sphinx's
built-in memory.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import shutil
import uuid
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from models import EnrichedPlaylist, AnalysisOutput

logger = logging.getLogger(__name__)

# Directory where per-user notebooks live
_SESSIONS_DIR = Path(__file__).parent / "_sphinx_sessions"
_SESSIONS_DIR.mkdir(exist_ok=True)

# Map of user_id -> { notebook_path, cell_count }
_SESSION_STATE: Dict[str, Dict[str, Any]] = {}

# Schema for structured Sphinx output when producing explanations (not plots)
_EXPLANATION_SCHEMA = json.dumps({
    "answer": {"type": "string", "description": "The full answer to the user's question in Markdown."},
})


# ═══════════════════════════════════════════════════════════════════════════
# Notebook creation helpers
# ═══════════════════════════════════════════════════════════════════════════

def _new_notebook() -> dict:
    """Return an empty Jupyter notebook dict (nbformat 4)."""
    return {
        "nbformat": 4,
        "nbformat_minor": 5,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.11"},
        },
        "cells": [],
    }


def _code_cell(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source.splitlines(keepends=True),
    }


def _markdown_cell(source: str) -> dict:
    return {
        "cell_type": "markdown",
        "metadata": {},
        "source": source.splitlines(keepends=True),
    }


def _analysis_output_to_serialisable(ao: AnalysisOutput) -> dict:
    """Minimal serialisation of an AnalysisOutput for notebook injection."""
    d = asdict(ao)
    return d


def _build_data_cell(
    enriched: List[EnrichedPlaylist],
    analyses: Optional[List[AnalysisOutput]] = None,
) -> str:
    """Python code string that injects analysis + enriched data as dicts."""
    ep_data = json.dumps([asdict(e) for e in enriched], default=str)
    lines = [
        "# ── OffBeat analysis data (auto-injected) ──",
        "import json, warnings",
        "warnings.filterwarnings('ignore')",
        "",
        f"enriched_playlists = json.loads('''{ep_data}''')",
        "",
    ]

    if analyses:
        an_data = json.dumps(
            [_analysis_output_to_serialisable(a) for a in analyses],
            default=str,
        )
        lines += [
            f"analysis_results = json.loads('''{an_data}''')",
            "",
        ]

    lines += [
        "# Convenience: flatten all tracks across playlists",
        "all_tracks = []",
        "for pl in enriched_playlists:",
        "    for t in pl.get('tracks', []):",
        "        t['_playlist_name'] = pl.get('name', '')",
        "        all_tracks.append(t)",
        f"print(f'Loaded {{len(enriched_playlists)}} playlists, {{len(all_tracks)}} total tracks')",
    ]
    return "\n".join(lines)


def _build_context_markdown(
    enriched: List[EnrichedPlaylist],
    analyses: Optional[List[AnalysisOutput]] = None,
) -> str:
    """Markdown cell describing the data so Sphinx has rich context."""
    parts = [
        "# OffBeat Playlist Analysis Session\n",
        "You have the following data loaded:\n",
    ]
    for ep in enriched:
        parts.append(f"- **{ep.name}** — {len(ep.tracks)} tracks  ")

    if analyses:
        parts.append("\n## Analysis Results\n")
        for ao in analyses:
            parts.append(f"### {ao.playlist_name}\n")
            parts.append(f"- Clusters: {len(ao.clusters)}")
            for c in ao.clusters:
                anomaly_ct = sum(1 for t in c.tracks if t.is_anomaly)
                parts.append(
                    f"  - **{c.label}** (cluster #{c.cluster_id}): "
                    f"{c.size} tracks, {anomaly_ct} anomalies, "
                    f"top tags: {', '.join(c.centroid_features.top_tags[:5])}"
                )
            summary = ao.summary
            parts.append(
                f"- Summary: {summary.num_tracks} total, "
                f"{summary.num_eligible} eligible, "
                f"{summary.num_anomalies} anomalies "
                f"(cutoff {summary.anomaly_score_cutoff:.2f})"
            )

    parts += [
        "\n---\n",
        "The user will ask questions about their playlist data. ",
        "You can reference `enriched_playlists`, `analysis_results`, "
        "and `all_tracks` variables. ",
        "For visualizations, use **matplotlib** or **plotly**. ",
        "For explanations, answer concisely in Markdown.",
    ]
    return "\n".join(parts)


# ═══════════════════════════════════════════════════════════════════════════
# Session management
# ═══════════════════════════════════════════════════════════════════════════

def create_session(
    user_id: str,
    enriched: List[EnrichedPlaylist],
    analyses: Optional[List[AnalysisOutput]] = None,
) -> str:
    """Create (or reset) a Sphinx notebook session for a user.

    Returns the session notebook path.
    """
    user_dir = _SESSIONS_DIR / user_id
    user_dir.mkdir(parents=True, exist_ok=True)

    nb = _new_notebook()
    nb["cells"].append(_markdown_cell(_build_context_markdown(enriched, analyses)))
    nb["cells"].append(_code_cell(_build_data_cell(enriched, analyses)))

    nb_path = user_dir / "session.ipynb"
    nb_path.write_text(json.dumps(nb, indent=1))

    _SESSION_STATE[user_id] = {
        "notebook_path": str(nb_path),
        "cell_count": len(nb["cells"]),
    }

    logger.info(f"[sphinx] Created session for {user_id} at {nb_path}")
    return str(nb_path)


def get_session(user_id: str) -> Optional[Dict[str, Any]]:
    """Return existing session state, or None."""
    return _SESSION_STATE.get(user_id)


def destroy_session(user_id: str) -> None:
    """Clean up a user session."""
    state = _SESSION_STATE.pop(user_id, None)
    if state:
        user_dir = _SESSIONS_DIR / user_id
        if user_dir.exists():
            shutil.rmtree(user_dir, ignore_errors=True)
    logger.info(f"[sphinx] Destroyed session for {user_id}")


# ═══════════════════════════════════════════════════════════════════════════
# Run Sphinx CLI
# ═══════════════════════════════════════════════════════════════════════════

async def run_sphinx(
    user_id: str,
    prompt: str,
    enriched: List[EnrichedPlaylist],
    analyses: Optional[List[AnalysisOutput]] = None,
    timeout_seconds: int = 120,
) -> Dict[str, Any]:
    """Run ``sphinx-cli chat`` and return parsed response.

    Creates the session notebook on first call; reuses it for follow-ups.

    Returns
    -------
    {
      "text": str,         # markdown answer text
      "images": [str],     # base64-encoded PNG images (if any)
      "code": [str],       # code cells Sphinx added (optional)
      "error": str | None  # error message if failed
    }
    """
    session = get_session(user_id)
    if not session:
        nb_path = create_session(user_id, enriched, analyses)
        session = _SESSION_STATE[user_id]
    else:
        nb_path = session["notebook_path"]

    prev_cell_count = session["cell_count"]

    # Build command
    sphinx_api_key = os.environ.get("SPHINX_API_KEY", "")
    cmd = [
        "sphinx-cli", "chat",
        "--notebook-filepath", nb_path,
        "--prompt", prompt,
        "--no-memory-read",
        "--no-memory-write",
        "--no-web-search",
        "--no-file-search",
        "--no-package-installation",
    ]

    env = {**os.environ}
    if sphinx_api_key:
        env["SPHINX_API_KEY"] = sphinx_api_key

    logger.info(f"[sphinx] Running: {' '.join(cmd[:6])}… (prompt: {prompt[:80]})")

    try:
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout_seconds
        )

        stdout_text = stdout.decode(errors="replace")
        stderr_text = stderr.decode(errors="replace")

        if proc.returncode != 0:
            logger.error(f"[sphinx] CLI failed (rc={proc.returncode}): {stderr_text[:500]}")
            return {
                "text": f"Sphinx encountered an error. Please try rephrasing your question.",
                "images": [],
                "code": [],
                "error": stderr_text[:500],
            }

        logger.info(f"[sphinx] CLI completed, parsing notebook…")

    except asyncio.TimeoutError:
        logger.error("[sphinx] CLI timed out")
        return {
            "text": "The request timed out. Try a simpler question.",
            "images": [],
            "code": [],
            "error": "timeout",
        }
    except FileNotFoundError:
        logger.error("[sphinx] sphinx-cli not found in PATH")
        return {
            "text": "Sphinx CLI is not installed on the server.",
            "images": [],
            "code": [],
            "error": "sphinx-cli not found",
        }

    # Parse the modified notebook for new cells
    return _parse_notebook_response(nb_path, prev_cell_count, user_id)


def _parse_notebook_response(
    nb_path: str,
    prev_cell_count: int,
    user_id: str,
) -> Dict[str, Any]:
    """Read the notebook and extract content from newly-added cells."""
    try:
        nb = json.loads(Path(nb_path).read_text())
    except Exception as e:
        logger.error(f"[sphinx] Failed to read notebook: {e}")
        return {
            "text": "Failed to read Sphinx response.",
            "images": [],
            "code": [],
            "error": str(e),
        }

    cells = nb.get("cells", [])
    new_cells = cells[prev_cell_count:]

    # Update session state
    if user_id in _SESSION_STATE:
        _SESSION_STATE[user_id]["cell_count"] = len(cells)

    text_parts: List[str] = []
    images: List[str] = []
    code_parts: List[str] = []

    for cell in new_cells:
        cell_type = cell.get("cell_type", "")
        source = "".join(cell.get("source", []))

        if cell_type == "markdown":
            text_parts.append(source)

        elif cell_type == "code":
            code_parts.append(source)

            # Extract outputs
            for output in cell.get("outputs", []):
                otype = output.get("output_type", "")

                # Stream output (print statements)
                if otype == "stream":
                    stream_text = "".join(output.get("text", []))
                    if stream_text.strip():
                        text_parts.append(f"```\n{stream_text.strip()}\n```")

                # Rich output (plots, HTML, etc.)
                data = output.get("data", {})

                if "image/png" in data:
                    png_b64 = data["image/png"]
                    # Already base64 in notebook format
                    if isinstance(png_b64, list):
                        png_b64 = "".join(png_b64)
                    images.append(png_b64.strip())

                if "text/html" in data:
                    html = "".join(data["text/html"]) if isinstance(data["text/html"], list) else data["text/html"]
                    text_parts.append(html)

                if "text/plain" in data and "image/png" not in data:
                    plain = "".join(data["text/plain"]) if isinstance(data["text/plain"], list) else data["text/plain"]
                    if plain.strip() and plain.strip() not in ("None",):
                        text_parts.append(f"```\n{plain.strip()}\n```")

                # Error output
                if otype == "error":
                    ename = output.get("ename", "Error")
                    evalue = output.get("evalue", "")
                    text_parts.append(f"**{ename}**: {evalue}")

    # Combine text
    combined_text = "\n\n".join(text_parts) if text_parts else "Analysis complete."

    return {
        "text": combined_text,
        "images": images,
        "code": code_parts,
        "error": None,
    }
