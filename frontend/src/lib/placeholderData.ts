/**
 * Placeholder analysis data derived from real playlist_analysis_insights.json.
 * Used to render the visualization UI immediately so users see the correct
 * layout even before the backend responds.
 *
 * Structure mirrors what the POST /analysis endpoint returns.
 */

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AudioMeans {
  acousticness: number;
  danceability: number;
  energy: number;
  instrumentalness: number;
  liveness: number;
  loudness: number;
  speechiness: number;
  tempo: number;
  valence: number;
}

export interface CentroidFeatures {
  audio_means: AudioMeans;
  top_tags: string[];
  tag_weights_top: Record<string, number>;
}

export interface AnalysisTrack {
  spotify_id: string;
  title: string;
  cluster_id: number;
  anomaly_score: number;
  is_anomaly: boolean;
  reason: string;
}

export interface Cluster {
  cluster_id: number;
  size: number;
  centroid_features: CentroidFeatures;
  tracks: AnalysisTrack[];
}

export interface Anomaly {
  spotify_id: string;
  title: string;
  cluster_id: number;
  anomaly_score: number;
  reason: string;
}

export interface PlaylistSummary {
  num_tracks: number;
  num_eligible: number;
  num_excluded_missing_all: number;
  num_excluded_insufficient_audio_cluster: number;
  num_clusters: number;
  num_anomalies: number;
  anomaly_score_cutoff: number;
}

export interface AnalysisPlaylist {
  playlist_id: string;
  playlist_name: string;
  summary: PlaylistSummary;
  clusters: Record<string, Cluster>;
  anomalies: Anomaly[];
}

export interface AnalysisResult {
  generated_at: string;
  num_playlists: number;
  playlists: AnalysisPlaylist[];
}

// ---------------------------------------------------------------------------
// Placeholder data — representative subset of real analysis output
// ---------------------------------------------------------------------------

export const PLACEHOLDER_ANALYSIS: AnalysisResult = {
  generated_at: "2026-02-22T09:13:50.367736+00:00",
  num_playlists: 2,
  playlists: [
    {
      playlist_id: "7qF4mOQrz3xPssEeYTc53q",
      playlist_name: "sahith songs",
      summary: {
        num_tracks: 701,
        num_eligible: 658,
        num_excluded_missing_all: 43,
        num_excluded_insufficient_audio_cluster: 0,
        num_clusters: 8,
        num_anomalies: 99,
        anomaly_score_cutoff: 0.773,
      },
      clusters: {
        high_energy_sad_fast: {
          cluster_id: 4,
          size: 102,
          centroid_features: {
            audio_means: {
              acousticness: 0.075,
              danceability: 0.688,
              energy: 0.674,
              instrumentalness: 0.002,
              liveness: 0.160,
              loudness: -5.07,
              speechiness: 0.074,
              tempo: 142.56,
              valence: 0.225,
            },
            top_tags: ["rap", "trap", "hip", "hop", "pop", "hip-hop", "rage", "cloud"],
            tag_weights_top: { rap: 0.133, trap: 0.109, hip: 0.065, hop: 0.065, pop: 0.058, "hip-hop": 0.044, rage: 0.042, cloud: 0.036 },
          },
          tracks: [
            { spotify_id: "3aQem4jVGdhtg116TmJnHz", title: "What's Next", cluster_id: 4, anomaly_score: 0.644, is_anomaly: false, reason: "" },
            { spotify_id: "08dz3ygXyFur6bL7Au8u8J", title: "Over", cluster_id: 4, anomaly_score: 0.658, is_anomaly: false, reason: "" },
            { spotify_id: "5UwhSyAaU6b5RHeYPzxZld", title: "LIL DEMON", cluster_id: 4, anomaly_score: 0.660, is_anomaly: false, reason: "" },
          ],
        },
        medium_energy_sad: {
          cluster_id: 6,
          size: 70,
          centroid_features: {
            audio_means: {
              acousticness: 0.129,
              danceability: 0.526,
              energy: 0.594,
              instrumentalness: 0.011,
              liveness: 0.173,
              loudness: -6.75,
              speechiness: 0.064,
              tempo: 101.53,
              valence: 0.241,
            },
            top_tags: ["rap", "trap", "rnb", "pop", "hop", "hip", "electronic", "soul"],
            tag_weights_top: { rap: 0.120, trap: 0.098, rnb: 0.070, pop: 0.065, hop: 0.058, hip: 0.055, electronic: 0.035, soul: 0.028 },
          },
          tracks: [
            { spotify_id: "3CDVMejYHnB1SkEEx0T1N4", title: "PRIDE.", cluster_id: 6, anomaly_score: 0.520, is_anomaly: false, reason: "" },
            { spotify_id: "1mWGaYN0MCECbiYWfaJwm6", title: "Snooze", cluster_id: 6, anomaly_score: 0.542, is_anomaly: false, reason: "" },
          ],
        },
        medium_energy_sad_fast: {
          cluster_id: 2,
          size: 90,
          centroid_features: {
            audio_means: {
              acousticness: 0.114,
              danceability: 0.727,
              energy: 0.609,
              instrumentalness: 0.001,
              liveness: 0.182,
              loudness: -6.51,
              speechiness: 0.314,
              tempo: 155.58,
              valence: 0.363,
            },
            top_tags: ["rap", "trap", "hop", "hip", "pop", "hip-hop", "southern", "lil"],
            tag_weights_top: { rap: 0.135, trap: 0.116, hop: 0.092, hip: 0.090, pop: 0.051, "hip-hop": 0.049, southern: 0.027, lil: 0.026 },
          },
          tracks: [
            { spotify_id: "2FvD20Z8aoWIePi7PoN8sG", title: "TOES (feat. Lil Baby & Moneybagg Yo)", cluster_id: 2, anomaly_score: 0.529, is_anomaly: false, reason: "" },
            { spotify_id: "5AqiaRGBPOmjUGaNPMaBb9", title: "Life Is Good (feat. Drake)", cluster_id: 2, anomaly_score: 0.540, is_anomaly: false, reason: "" },
          ],
        },
        high_energy_neutral: {
          cluster_id: 5,
          size: 74,
          centroid_features: {
            audio_means: {
              acousticness: 0.198,
              danceability: 0.684,
              energy: 0.685,
              instrumentalness: 0.0,
              liveness: 0.195,
              loudness: -6.32,
              speechiness: 0.302,
              tempo: 96.89,
              valence: 0.524,
            },
            top_tags: ["hip", "hop", "rap", "hip-hop", "west", "conscious", "kanye", "trap"],
            tag_weights_top: { hip: 0.139, hop: 0.138, rap: 0.114, "hip-hop": 0.101, west: 0.073, conscious: 0.063, kanye: 0.063, trap: 0.046 },
          },
          tracks: [
            { spotify_id: "3s7MCdkMT6eDgvmOJhtPcz", title: "All Of The Lights", cluster_id: 5, anomaly_score: 0.410, is_anomaly: false, reason: "" },
            { spotify_id: "7nPhf1YW1gZZP8kN6kn5fQ", title: "Gorgeous", cluster_id: 5, anomaly_score: 0.450, is_anomaly: false, reason: "" },
          ],
        },
        high_energy_happy: {
          cluster_id: 7,
          size: 86,
          centroid_features: {
            audio_means: {
              acousticness: 0.160,
              danceability: 0.769,
              energy: 0.714,
              instrumentalness: 0.001,
              liveness: 0.159,
              loudness: -5.29,
              speechiness: 0.097,
              tempo: 127.30,
              valence: 0.672,
            },
            top_tags: ["rap", "pop", "trap", "rnb", "hip", "hop", "hip-hop", "kpop"],
            tag_weights_top: { rap: 0.099, pop: 0.092, trap: 0.086, rnb: 0.044, hip: 0.040, hop: 0.040, "hip-hop": 0.034, kpop: 0.030 },
          },
          tracks: [
            { spotify_id: "4h9wh7iOZ0GGn8QVp4RAOB", title: "I Ain't Worried", cluster_id: 7, anomaly_score: 0.482, is_anomaly: false, reason: "" },
            { spotify_id: "2LBqCSwhJGcFQeTHMVGwy3", title: "Die For You", cluster_id: 7, anomaly_score: 0.500, is_anomaly: false, reason: "" },
          ],
        },
      },
      anomalies: [
        { spotify_id: "3CDVMejYHnB1SkEEx0T1N4", title: "Many Men", cluster_id: 6, anomaly_score: 1.0, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=1.00. lower tempo by 65 BPM; higher loudness by 0.7 dB; higher energy by 0.12" },
        { spotify_id: "5DxDLsW6PsLz5gkwC7Mk5S", title: "Free", cluster_id: 4, anomaly_score: 0.904, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.90. lower tempo by 3 BPM; lower loudness by 0.5 dB; higher valence by 0.21" },
        { spotify_id: "5wNIHa6wvCCKP6fWgo3UAh", title: "CHAMPAIN & VACAY", cluster_id: 2, anomaly_score: 0.877, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.88. higher tempo by 3 BPM; lower loudness by 0.8 dB; lower danceability by 0.15" },
        { spotify_id: "6cfVDaIdvDtYH91RqC6Wox", title: "Hol' Up", cluster_id: 5, anomaly_score: 0.876, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.88. higher tempo by 13 BPM; higher acousticness by 0.71; higher valence by 0.35" },
        { spotify_id: "7lsYGc5H5DHktxO7gbB8bN", title: "Ordinary Life", cluster_id: 6, anomaly_score: 0.869, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.87. higher tempo by 7 BPM; lower loudness by 2.4 dB; lower danceability by 0.14" },
        { spotify_id: "4vqwVaEqLNWo3UXhQi5IFH", title: "FLORIDA FLOW", cluster_id: 2, anomaly_score: 0.865, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.86. lower tempo by 18 BPM; lower loudness by 1.3 dB; higher speechiness by 0.15" },
        { spotify_id: "0IX5OFffosy8wk16m1IFCa", title: "Drugs N Hella Melodies (feat. Kali Uchis)", cluster_id: 4, anomaly_score: 0.861, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.86. higher tempo by 4 BPM; lower loudness by 1.8 dB; higher acousticness by 0.19" },
        { spotify_id: "03auLpFLdCv4HozP4pQseu", title: "ATM", cluster_id: 2, anomaly_score: 0.859, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.86. higher tempo by 27 BPM; lower loudness by 1.1 dB; higher acousticness by 0.24" },
        { spotify_id: "38HkYfvnhHLLB5Yaj2VpZg", title: "No Photos", cluster_id: 7, anomaly_score: 0.848, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.85. lower tempo by 9 BPM; lower loudness by 0.4 dB; higher acousticness by 0.22" },
        { spotify_id: "1I37Zz2g3hk9eWxaNkj031", title: "90210 (feat. Kacy Hill)", cluster_id: 4, anomaly_score: 0.840, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.84. lower tempo by 55 BPM; lower loudness by 1.2 dB; higher acousticness by 0.08" },
        { spotify_id: "5nCaV4M3sTPGCu4lQ7n8iJ", title: "Heartless", cluster_id: 4, anomaly_score: 0.832, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.83. higher tempo by 8 BPM; higher valence by 0.31; lower danceability by 0.12" },
        { spotify_id: "7qPksyJaBsK25MJFkXn2Jl", title: "Laugh Now Cry Later", cluster_id: 7, anomaly_score: 0.821, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.82. lower tempo by 10 BPM; higher valence by 0.28; higher acousticness by 0.15" },
      ],
    },
    {
      playlist_id: "19UHSXDaXJqjYSLS53ZL1Z",
      playlist_name: "hype",
      summary: {
        num_tracks: 255,
        num_eligible: 238,
        num_excluded_missing_all: 17,
        num_excluded_insufficient_audio_cluster: 0,
        num_clusters: 7,
        num_anomalies: 36,
        anomaly_score_cutoff: 0.806,
      },
      clusters: {
        high_energy_neutral: {
          cluster_id: 0,
          size: 24,
          centroid_features: {
            audio_means: {
              acousticness: 0.085,
              danceability: 0.620,
              energy: 0.780,
              instrumentalness: 0.003,
              liveness: 0.210,
              loudness: -4.50,
              speechiness: 0.120,
              tempo: 130.50,
              valence: 0.510,
            },
            top_tags: ["rap", "trap", "hype", "electronic", "bass", "edm", "energy", "pop"],
            tag_weights_top: { rap: 0.145, trap: 0.130, hype: 0.095, electronic: 0.070, bass: 0.055, edm: 0.048, energy: 0.040, pop: 0.035 },
          },
          tracks: [
            { spotify_id: "abc123", title: "Sicko Mode", cluster_id: 0, anomaly_score: 0.350, is_anomaly: false, reason: "" },
            { spotify_id: "def456", title: "HUMBLE.", cluster_id: 0, anomaly_score: 0.380, is_anomaly: false, reason: "" },
          ],
        },
        medium_energy_sad_fast: {
          cluster_id: 1,
          size: 40,
          centroid_features: {
            audio_means: {
              acousticness: 0.095,
              danceability: 0.710,
              energy: 0.620,
              instrumentalness: 0.001,
              liveness: 0.175,
              loudness: -6.20,
              speechiness: 0.290,
              tempo: 148.80,
              valence: 0.340,
            },
            top_tags: ["rap", "trap", "hop", "hip", "hip-hop", "southern", "dark", "melodic"],
            tag_weights_top: { rap: 0.140, trap: 0.118, hop: 0.088, hip: 0.085, "hip-hop": 0.052, southern: 0.030, dark: 0.028, melodic: 0.025 },
          },
          tracks: [
            { spotify_id: "ghi789", title: "XO Tour Llif3", cluster_id: 1, anomaly_score: 0.450, is_anomaly: false, reason: "" },
          ],
        },
        high_energy_happy: {
          cluster_id: 5,
          size: 31,
          centroid_features: {
            audio_means: {
              acousticness: 0.140,
              danceability: 0.780,
              energy: 0.740,
              instrumentalness: 0.001,
              liveness: 0.150,
              loudness: -4.90,
              speechiness: 0.085,
              tempo: 122.40,
              valence: 0.700,
            },
            top_tags: ["pop", "rap", "dance", "rnb", "party", "hip-hop", "trap", "summer"],
            tag_weights_top: { pop: 0.110, rap: 0.098, dance: 0.082, rnb: 0.060, party: 0.050, "hip-hop": 0.042, trap: 0.038, summer: 0.030 },
          },
          tracks: [
            { spotify_id: "jkl012", title: "Levitating", cluster_id: 5, anomaly_score: 0.320, is_anomaly: false, reason: "" },
          ],
        },
        high_energy_sad_fast: {
          cluster_id: 6,
          size: 39,
          centroid_features: {
            audio_means: {
              acousticness: 0.065,
              danceability: 0.695,
              energy: 0.700,
              instrumentalness: 0.002,
              liveness: 0.155,
              loudness: -4.80,
              speechiness: 0.080,
              tempo: 145.20,
              valence: 0.210,
            },
            top_tags: ["rap", "trap", "rage", "cloud", "hip-hop", "dark", "bass", "electronic"],
            tag_weights_top: { rap: 0.140, trap: 0.120, rage: 0.065, cloud: 0.050, "hip-hop": 0.042, dark: 0.038, bass: 0.030, electronic: 0.028 },
          },
          tracks: [
            { spotify_id: "mno345", title: "Rockstar", cluster_id: 6, anomaly_score: 0.500, is_anomaly: false, reason: "" },
          ],
        },
      },
      anomalies: [
        { spotify_id: "pqr678", title: "Blinding Lights", cluster_id: 5, anomaly_score: 0.920, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.92. higher valence by 0.45; lower speechiness by 0.20; higher acousticness by 0.18" },
        { spotify_id: "stu901", title: "Save Your Tears", cluster_id: 5, anomaly_score: 0.880, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.88. higher valence by 0.38; higher acousticness by 0.25; lower energy by 0.10" },
        { spotify_id: "vwx234", title: "Starboy", cluster_id: 0, anomaly_score: 0.850, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.85. lower tempo by 20 BPM; higher valence by 0.30; higher danceability by 0.12" },
        { spotify_id: "yza567", title: "The Hills", cluster_id: 6, anomaly_score: 0.830, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.83. lower tempo by 42 BPM; lower energy by 0.15; higher acousticness by 0.22" },
        { spotify_id: "bcd890", title: "Party Monster", cluster_id: 1, anomaly_score: 0.815, reason: "Anomalous vs dominant mood 'high_energy_sad_fast'. distance_score=0.82. lower tempo by 15 BPM; higher valence by 0.18; lower speechiness by 0.12" },
      ],
    },
  ],
};

// ---------------------------------------------------------------------------
// Helper: compute aggregate stats across all playlists
// ---------------------------------------------------------------------------

export function getOverallStats(data: AnalysisResult) {
  const totalTracks = data.playlists.reduce((s, p) => s + p.summary.num_tracks, 0);
  const totalEligible = data.playlists.reduce((s, p) => s + p.summary.num_eligible, 0);
  const totalClusters = data.playlists.reduce((s, p) => s + Object.keys(p.clusters).length, 0);
  const totalAnomalies = data.playlists.reduce((s, p) => s + p.summary.num_anomalies, 0);
  return { totalTracks, totalEligible, totalClusters, totalAnomalies };
}

/** Audio feature labels & color mapping for visualizations */
export const AUDIO_FEATURE_META: Record<
  keyof AudioMeans,
  { label: string; color: string; unit: string; min: number; max: number }
> = {
  energy:           { label: "Energy",           color: "bg-brand-cyan",      unit: "%", min: 0, max: 1 },
  danceability:     { label: "Danceability",     color: "bg-brand-magenta",   unit: "%", min: 0, max: 1 },
  valence:          { label: "Valence",          color: "bg-yellow-400",      unit: "%", min: 0, max: 1 },
  acousticness:     { label: "Acousticness",     color: "bg-green-400",       unit: "%", min: 0, max: 1 },
  speechiness:      { label: "Speechiness",      color: "bg-orange-400",      unit: "%", min: 0, max: 1 },
  instrumentalness: { label: "Instrumentalness", color: "bg-purple-400",      unit: "%", min: 0, max: 1 },
  liveness:         { label: "Liveness",         color: "bg-brand-teal",      unit: "%", min: 0, max: 1 },
  loudness:         { label: "Loudness",         color: "bg-red-400",         unit: "dB", min: -20, max: 0 },
  tempo:            { label: "Tempo",            color: "bg-brand-lavender",  unit: "BPM", min: 60, max: 200 },
};

/** Parse an anomaly reason string into structured deviation objects */
export function parseAnomalyReason(reason: string): {
  dominantMood: string;
  distanceScore: number;
  deviations: { feature: string; direction: "higher" | "lower"; amount: string }[];
} {
  const moodMatch = reason.match(/dominant mood '([^']+)'/);
  const distMatch = reason.match(/distance_score=([\d.]+)/);
  const devRegex = /(higher|lower) (\w+) by ([\d.]+ \w+)/g;
  const deviations: { feature: string; direction: "higher" | "lower"; amount: string }[] = [];
  let m: RegExpExecArray | null;
  while ((m = devRegex.exec(reason)) !== null) {
    deviations.push({ feature: m[2], direction: m[1] as "higher" | "lower", amount: m[3] });
  }
  return {
    dominantMood: moodMatch?.[1] ?? "",
    distanceScore: distMatch ? parseFloat(distMatch[1]) : 0,
    deviations,
  };
}
