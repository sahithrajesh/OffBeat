/**
 * Typed API service layer.
 *
 * Every backend endpoint gets a dedicated function here so the UI
 * never has to know about URL paths or request shapes.  All calls
 * go through `apiFetch` which attaches the Bearer JWT automatically.
 */

import { apiFetch } from "./auth";

// ---------------------------------------------------------------------------
// Shared types (mirror the backend Pydantic / dataclass models)
// ---------------------------------------------------------------------------

export interface Artist {
  name: string;
  spotify_id?: string;
}

export interface AudioFeatures {
  acousticness: number;
  danceability: number;
  energy: number;
  instrumentalness: number;
  liveness: number;
  loudness: number;
  speechiness: number;
  tempo: number;
  valence: number;
  key?: number;
  mode?: number;
}

export interface Tag {
  name: string;
  count: number;
}

export interface EnrichedTrack {
  spotify_id: string;
  title: string;
  artists: Artist[];
  album_name: string;
  duration_ms: number;
  audio_features?: AudioFeatures;
  tags: Tag[];
  reccobeats_id?: string;
}

export interface Playlist {
  spotify_id: string;
  name: string;
  total_tracks: number;
  owner: string;
  description?: string;
  image_url?: string;
}

export interface EnrichedPlaylist {
  spotify_id: string;
  name: string;
  tracks: EnrichedTrack[];
  description?: string;
  owner?: string;
  snapshot_id?: string;
  image_url?: string;
  total_tracks: number;
}

export interface UserProfile {
  spotify_id: string;
  display_name: string;
  email: string;
  avatar_url: string;
}

// ---------------------------------------------------------------------------
// Auth
// ---------------------------------------------------------------------------

/** GET /auth/me — current user profile */
export function fetchMe(): Promise<UserProfile> {
  return apiFetch<UserProfile>("/auth/me");
}

// ---------------------------------------------------------------------------
// Playlists
// ---------------------------------------------------------------------------

/** GET /playlists — user's Spotify playlists */
export function fetchPlaylists(signal?: AbortSignal): Promise<Playlist[]> {
  return apiFetch<Playlist[]>("/playlists", { signal });
}

/** POST /create — create a Spotify playlist from tracks */
export function createPlaylist(tracks: EnrichedTrack[]): Promise<unknown> {
  return apiFetch("/create", {
    method: "POST",
    body: JSON.stringify(tracks),
  });
}

// ---------------------------------------------------------------------------
// Analysis & recommendations
// ---------------------------------------------------------------------------

/** GET /analysis — fetch the pre-computed playlist analysis insights */
export function fetchAnalysis(): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/analysis");
}

/** POST /compare — compare a playlist against analysis data */
export function comparePlaylist(
  analysisData: Record<string, unknown>,
  playlist: Playlist,
): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/compare", {
    method: "POST",
    body: JSON.stringify({ analysis_data: analysisData, playlist }),
  });
}

/** POST /basic — generate recommendations from analysis data */
export function basicRecommendations(
  analysisData: Record<string, unknown>,
): Promise<EnrichedPlaylist> {
  return apiFetch<EnrichedPlaylist>("/basic", {
    method: "POST",
    body: JSON.stringify(analysisData),
  });
}

/** POST /anomaly — anomaly-based recommendations from analysis data */
export function anomalyRecommendations(
  analysisData: Record<string, unknown>,
): Promise<EnrichedPlaylist> {
  return apiFetch<EnrichedPlaylist>("/anomaly", {
    method: "POST",
    body: JSON.stringify(analysisData),
  });
}
