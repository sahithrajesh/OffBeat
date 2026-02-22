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

import type {
  AnalysisResult,
  AnalysisPlaylist,
  AnalysisTrack,
  Cluster,
  Anomaly,
} from "./placeholderData";

/** Raw backend response shape (clusters as array). */
interface RawCluster {
  cluster_id: number;
  label: string;
  size: number;
  centroid_features: {
    audio_means: Record<string, number | null>;
    top_tags: string[];
    tag_weights_top: Record<string, number>;
  };
  member_track_ids: string[];
  tracks: AnalysisTrack[];
}

interface RawAnalysisPlaylist {
  playlist_id: string;
  playlist_name: string;
  clusters: RawCluster[];
  moods: Record<string, unknown>;
  summary: AnalysisPlaylist["summary"];
}

interface RawAnalysisResponse {
  num_playlists: number;
  playlists: RawAnalysisPlaylist[];
}

/** Transform the new backend response (clusters array) into the
 *  frontend `AnalysisResult` shape (clusters Record + flat anomalies). */
function transformAnalysisResponse(raw: RawAnalysisResponse): AnalysisResult {
  return {
    generated_at: new Date().toISOString(),
    num_playlists: raw.num_playlists,
    playlists: raw.playlists.map((p) => {
      // Array → Record keyed by label
      const clusters: Record<string, Cluster> = {};
      for (const c of p.clusters) {
        clusters[c.label] = {
          cluster_id: c.cluster_id,
          size: c.size,
          centroid_features: {
            audio_means: Object.fromEntries(
              Object.entries(c.centroid_features.audio_means).map(([k, v]) => [k, v ?? 0]),
            ) as unknown as Cluster["centroid_features"]["audio_means"],
            top_tags: c.centroid_features.top_tags,
            tag_weights_top: c.centroid_features.tag_weights_top,
          },
          tracks: c.tracks,
        };
      }

      // Extract anomalies from cluster tracks
      const anomalies: Anomaly[] = [];
      for (const c of p.clusters) {
        for (const t of c.tracks) {
          if (t.is_anomaly) {
            anomalies.push({
              spotify_id: t.spotify_id,
              title: t.title,
              cluster_id: t.cluster_id ?? c.cluster_id,
              anomaly_score: t.anomaly_score,
              reason: t.reason,
            });
          }
        }
      }
      anomalies.sort((a, b) => b.anomaly_score - a.anomaly_score);

      return {
        playlist_id: p.playlist_id,
        playlist_name: p.playlist_name,
        summary: p.summary,
        clusters,
        anomalies,
      };
    }),
  };
}

/**
 * POST /analysis — enrich + analyse selected playlists.
 * Returns an `AnalysisResult` ready for the UI.
 */
export async function analyzePlaylists(
  playlistIds: string[],
): Promise<AnalysisResult> {
  const raw = await apiFetch<RawAnalysisResponse>("/analysis", {
    method: "POST",
    body: JSON.stringify(playlistIds),
  });
  return transformAnalysisResponse(raw);
}

/** POST /compare — compare playlists by mood distribution */
export function comparePlaylists(
  playlistIds: string[],
): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/compare", {
    method: "POST",
    body: JSON.stringify(playlistIds),
  });
}

/** POST /basic — generate recommendations for selected playlists */
export function basicRecommendations(
  playlistIds: string[],
): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/basic", {
    method: "POST",
    body: JSON.stringify(playlistIds),
  });
}

/** POST /anomaly — get anomaly tracks from selected playlists */
export function fetchAnomalies(
  playlistIds: string[],
): Promise<Record<string, unknown>> {
  return apiFetch<Record<string, unknown>>("/anomaly", {
    method: "POST",
    body: JSON.stringify(playlistIds),
  });
}
