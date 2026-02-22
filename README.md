# OffBeat

https://off-beat.tech

OffBeat is a web app that analyzes your Spotify playlists to understand their core moods, spot outlier tracks, and help you reshape your listening experience. It combines Spotify metadata with audio features from ReccoBeats and social tags from Last.fm to build a rich “mood profile” for every song.

---

## Features

- **Playlist analysis (core action)**  
  - Cluster songs into mood groups (e.g., high‑energy happy vs. low‑energy mellow).  
  - Compute anomaly scores to flag “off‑beat” songs that don’t match the main mood.  
  - Produce human‑readable explanations for why a track is considered an anomaly.

- **Playlist comparisons**  
  - Compare multiple playlists by their mood distributions.  
  - See which moods are shared and how strongly each playlist leans into them.

- **Mood selection**  
  - Pick a mood label (e.g., “chill”, “high_energy_happy”).  
  - Surface tracks that match that mood across your selected playlists.

- **Anomaly‑based recommendations**  
  - For each anomaly, generate recommendation requests for Last.fm and ReccoBeats.  
  - Suggest tracks that better fit the playlist’s dominant mood or extend the anomaly’s vibe.

- **Mood‑based recommendations**  
  - Build mood‑aware recommendation contexts for Last.fm/ReccoBeats based on clusters.  
  - Use the returned candidates to expand a mood you like.

- **Sphinx‑powered analysis & chatbot**  
  - Sphinx drives the data science logic inside notebooks (feature extraction, clustering, anomaly detection).  
  - A Sphinx chatbot can answer questions like “Why is this track an anomaly?” or “Which playlist is the most energetic?”.

- **One‑click playlist creation**  
  - Turn any result set (anomalies, mood clusters, recommendations) into a new Spotify playlist.

---

## High‑Level Architecture

- **Data ingestion**
  - Spotify Web API for auth, playlists, and basic track metadata.
  - ReccoBeats API for audio features (acousticness, danceability, energy, etc.).
  - Last.fm API for social tags and mood‑related labels.

- **Core data model**
  - `EnrichedTrack`: Spotify metadata + ReccoBeats audio features + Last.fm tags.
  - `EnrichedPlaylist`: a playlist containing a list of `EnrichedTrack`s.

- **Analysis layer (Sphinx + Python)**
  - Notebook‑driven pipeline using Sphinx as an agent.
  - Key functions:
    - `run_playlist_analysis(enriched_playlist)` – clustering + anomaly detection.
    - `compare_playlists(playlists)` – mood‑label‑based comparison.
    - `select_tracks_by_mood(playlists, mood_label)`
    - `recommend_for_anomalies(playlists)` – builds payloads for external recommenders.
    - `recommend_for_mood(playlists, mood_label)` – mood‑based rec contexts.

- **Backend API**
  - Endpoints to trigger analysis, fetch insights, call Last.fm/ReccoBeats recommenders, and create Spotify playlists.

- **Frontend**
  - Auth and playlist selection.
  - Views for mood clusters, anomalies, playlist comparisons, mood selection, and recommendations.
  - Embedded chat UI that proxies questions to the Sphinx notebook.
