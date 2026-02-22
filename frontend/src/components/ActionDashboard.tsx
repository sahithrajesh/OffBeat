import { useState, useEffect, useCallback, useMemo } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import { ArrowRight, Loader2, AlertTriangle, Menu, X, ChevronDown, ChevronUp, ArrowUpRight, ArrowDownRight, Music2 } from 'lucide-react';
import type { Playlist, EnrichedPlaylist } from '@/lib/api';
import {
  runAnalysis,
  comparePlaylist,
  basicRecommendations,
  anomalyRecommendations,
  createPlaylist,
} from '@/lib/api';
import {
  AUDIO_FEATURE_META,
  parseAnomalyReason,
  type AnalysisResult,
  type AnalysisPlaylist,
  type Anomaly,
  type AudioMeans,
} from '@/lib/placeholderData';

/** Human-readable labels for backend action keys */
const ACTION_LABELS: Record<string, string> = {
  analysis: 'Playlist Analysis',
  compare: 'Playlist Comparisons',
  basic: 'Recommendations',
  anomaly: 'Anomaly Detection',
};

// ── Color palette for clusters (cycles) ──
const CLUSTER_COLORS = [
  { bg: 'bg-brand-cyan/10', border: 'border-brand-cyan/30', text: 'text-brand-cyan', bar: 'bg-brand-cyan' },
  { bg: 'bg-brand-magenta/10', border: 'border-brand-magenta/30', text: 'text-brand-magenta', bar: 'bg-brand-magenta' },
  { bg: 'bg-yellow-400/10', border: 'border-yellow-400/30', text: 'text-yellow-400', bar: 'bg-yellow-400' },
  { bg: 'bg-green-400/10', border: 'border-green-400/30', text: 'text-green-400', bar: 'bg-green-400' },
  { bg: 'bg-orange-400/10', border: 'border-orange-400/30', text: 'text-orange-400', bar: 'bg-orange-400' },
  { bg: 'bg-purple-400/10', border: 'border-purple-400/30', text: 'text-purple-400', bar: 'bg-purple-400' },
  { bg: 'bg-brand-teal/10', border: 'border-brand-teal/30', text: 'text-brand-teal', bar: 'bg-brand-teal' },
  { bg: 'bg-brand-lavender/10', border: 'border-brand-lavender/30', text: 'text-brand-lavender', bar: 'bg-brand-lavender' },
];

// ── Feature bar mini-component ──
function FeatureBar({ label, value, unit, color }: { label: string; value: number; max?: number; unit: string; color: string }) {
  const pct = unit === 'dB'
    ? ((value - (-20)) / 20) * 100 // loudness: -20→0 maps to 0→100
    : unit === 'BPM'
      ? ((value - 60) / 140) * 100 // tempo: 60→200 maps to 0→100
      : value * 100;
  const displayVal = unit === '%' ? `${(value * 100).toFixed(0)}%` : unit === 'BPM' ? `${value.toFixed(0)} BPM` : `${value.toFixed(1)} dB`;
  return (
    <div>
      <div className="flex justify-between text-[11px] mb-1">
        <span className="text-brand-lavender/70">{label}</span>
        <span className="text-white/80 font-mono">{displayVal}</span>
      </div>
      <div className="h-1.5 w-full rounded-full bg-white/5 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all duration-700 ease-out ${color}`}
          style={{ width: `${Math.max(0, Math.min(100, pct))}%` }}
        />
      </div>
    </div>
  );
}

// ── Anomaly card component ──
function AnomalyCard({ anomaly }: { anomaly: Anomaly }) {
  const [expanded, setExpanded] = useState(false);
  const parsed = useMemo(() => parseAnomalyReason(anomaly.reason), [anomaly.reason]);
  const scoreColor = anomaly.anomaly_score >= 0.9 ? 'text-red-400 bg-red-500/15 border-red-500/30'
    : anomaly.anomaly_score >= 0.85 ? 'text-orange-400 bg-orange-500/15 border-orange-500/30'
    : 'text-yellow-400 bg-yellow-500/15 border-yellow-500/30';

  return (
    <div
      className={`rounded-xl border transition-all duration-300 ${expanded ? 'bg-white/[0.03] border-white/10' : 'bg-white/[0.01] border-white/5 hover:bg-white/[0.02]'}`}
    >
      <button
        className="w-full flex items-center gap-3 sm:gap-4 p-3 sm:p-4 text-left"
        onClick={() => setExpanded(!expanded)}
      >
        {/* Score circle */}
        <div className={`w-10 h-10 sm:w-11 sm:h-11 rounded-xl border flex items-center justify-center shrink-0 font-mono text-xs font-bold ${scoreColor}`}>
          {(anomaly.anomaly_score * 100).toFixed(0)}
        </div>
        {/* Title & cluster */}
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-white truncate">{anomaly.title}</div>
          <div className="text-[11px] text-brand-teal/50 mt-0.5">
            Cluster: <span className="text-brand-teal/70 capitalize">{parsed.dominantMood.replace(/_/g, ' ') || `#${anomaly.cluster_id}`}</span>
          </div>
        </div>
        {/* Expand toggle */}
        <div className="shrink-0 text-brand-teal/40">
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </button>

      {expanded && (
        <div className="px-3 sm:px-4 pb-3 sm:pb-4 pt-0 space-y-3 animate-in slide-in-from-top-2 duration-200">
          {/* Deviation chips */}
          <div className="flex flex-wrap gap-1.5">
            {parsed.deviations.map((d, i) => (
              <span key={i} className={`inline-flex items-center gap-1 px-2 py-1 rounded-lg text-[11px] font-medium border ${
                d.direction === 'higher'
                  ? 'bg-red-500/10 text-red-300 border-red-500/20'
                  : 'bg-blue-500/10 text-blue-300 border-blue-500/20'
              }`}>
                {d.direction === 'higher' ? <ArrowUpRight size={11} /> : <ArrowDownRight size={11} />}
                {d.feature} {d.direction === 'higher' ? '+' : '−'}{d.amount}
              </span>
            ))}
          </div>
          {/* Full reason */}
          <p className="text-[11px] text-brand-teal/50 leading-relaxed">{anomaly.reason}</p>
        </div>
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Analysis Renderer — rich multi-playlist analysis view
// ═══════════════════════════════════════════════════════════════════════════
function AnalysisView({ data }: { data: AnalysisResult }) {
  const [activePlaylist, setActivePlaylist] = useState(0);
  const [expandedCluster, setExpandedCluster] = useState<string | null>(null);
  const playlist = data.playlists[activePlaylist];

  return (
    <div className="space-y-6 sm:space-y-10 animate-in fade-in duration-700">
      {/* Playlist tabs (if multiple) */}
      {data.playlists.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-2 -mb-2 scrollbar-none">
          {data.playlists.map((p, i) => (
            <button
              key={p.playlist_id}
              onClick={() => { setActivePlaylist(i); setExpandedCluster(null); }}
              className={`shrink-0 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-300 border ${
                i === activePlaylist
                  ? 'bg-brand-cyan/15 border-brand-cyan/40 text-brand-cyan shadow-[0_0_15px_rgba(0,158,250,0.1)]'
                  : 'bg-white/[0.02] border-white/5 text-brand-teal/60 hover:text-white hover:border-white/10'
              }`}
            >
              {p.playlist_name}
            </button>
          ))}
        </div>
      )}

      {/* Summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 sm:gap-4">
        <SummaryCard value={playlist.summary.num_tracks} label="Total Tracks" color="text-white" />
        <SummaryCard value={playlist.summary.num_eligible} label="Analyzed" color="text-brand-cyan" />
        <SummaryCard value={Object.keys(playlist.clusters).length} label="Clusters" color="text-brand-magenta" />
        <SummaryCard value={playlist.summary.num_anomalies} label="Outliers" color="text-red-400" accent />
      </div>

      {/* Coverage bar */}
      <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 sm:p-5">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs text-brand-teal/60 uppercase tracking-wider font-semibold">Cluster Distribution</span>
          <span className="text-xs text-brand-teal/50">{playlist.summary.num_eligible} eligible tracks</span>
        </div>
        <div className="flex h-3 rounded-full overflow-hidden gap-0.5">
          {Object.entries(playlist.clusters).map(([name, cluster], i) => {
            const pct = (cluster.size / playlist.summary.num_eligible) * 100;
            const c = CLUSTER_COLORS[i % CLUSTER_COLORS.length];
            return (
              <div
                key={name}
                className={`${c.bar} rounded-sm transition-all duration-500 relative group`}
                style={{ width: `${pct}%` }}
                title={`${name.replace(/_/g, ' ')}: ${cluster.size} tracks (${pct.toFixed(1)}%)`}
              />
            );
          })}
        </div>
        {/* Legend */}
        <div className="flex flex-wrap gap-x-4 gap-y-1.5 mt-3">
          {Object.entries(playlist.clusters).map(([name, cluster], i) => {
            const c = CLUSTER_COLORS[i % CLUSTER_COLORS.length];
            return (
              <div key={name} className="flex items-center gap-1.5">
                <div className={`w-2.5 h-2.5 rounded-sm ${c.bar}`} />
                <span className="text-[11px] text-brand-teal/70 capitalize">{name.replace(/_/g, ' ')} ({cluster.size})</span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Cluster cards */}
      <div>
        <h3 className="text-lg sm:text-xl font-bold text-white mb-4 sm:mb-5">Sonic Personas</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-4">
          {Object.entries(playlist.clusters).map(([clusterName, cluster], idx) => {
            const c = CLUSTER_COLORS[idx % CLUSTER_COLORS.length];
            const isExpanded = expandedCluster === clusterName;
            const audio = cluster.centroid_features.audio_means;
            // Show top features: energy, danceability, valence, tempo, + expand for all
            const primaryFeatures: (keyof AudioMeans)[] = ['energy', 'danceability', 'valence', 'acousticness'];
            const allFeatures = Object.keys(AUDIO_FEATURE_META) as (keyof AudioMeans)[];

            return (
              <div
                key={clusterName}
                className={`border rounded-xl sm:rounded-2xl transition-all duration-300 ${isExpanded ? `${c.bg} ${c.border}` : 'bg-white/[0.02] border-white/5 hover:border-white/10'}`}
              >
                {/* Card header */}
                <button
                  className="w-full text-left p-4 sm:p-5 flex items-start justify-between gap-3"
                  onClick={() => setExpandedCluster(isExpanded ? null : clusterName)}
                >
                  <div className="min-w-0">
                    <h4 className={`text-sm sm:text-base font-bold capitalize ${isExpanded ? c.text : 'text-white'}`}>
                      {clusterName.replace(/_/g, ' ')}
                    </h4>
                    <p className="text-xs text-brand-teal/50 mt-0.5">{cluster.size} tracks · Cluster #{cluster.cluster_id}</p>
                  </div>
                  <div className={`shrink-0 w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${c.bg} ${c.text} ${c.border} border`}>
                    {cluster.size}
                  </div>
                </button>

                {/* Primary features (always visible) */}
                <div className="px-4 sm:px-5 pb-3 space-y-2.5">
                  {primaryFeatures.map((feat) => {
                    const meta = AUDIO_FEATURE_META[feat];
                    return <FeatureBar key={feat} label={meta.label} value={audio[feat]} max={meta.max} unit={meta.unit} color={c.bar} />;
                  })}
                </div>

                {/* Tags */}
                <div className="px-4 sm:px-5 pb-3 flex flex-wrap gap-1.5">
                  {cluster.centroid_features.top_tags.slice(0, isExpanded ? 8 : 4).map((tag) => (
                    <Badge key={tag} variant="outline" className={`text-[10px] sm:text-[11px] bg-black/20 ${isExpanded ? `${c.border} ${c.text}` : 'border-white/10 text-brand-teal/70'}`}>
                      {tag}
                    </Badge>
                  ))}
                </div>

                {/* Expanded: all audio features + tag weights + track sample */}
                {isExpanded && (
                  <div className="px-4 sm:px-5 pb-4 sm:pb-5 space-y-5 animate-in slide-in-from-top-2 duration-300">
                    <div className="border-t border-white/5 pt-4">
                      <p className="text-[11px] text-brand-teal/50 uppercase tracking-wider font-semibold mb-3">All Audio Features</p>
                      <div className="space-y-2">
                        {allFeatures.filter(f => !primaryFeatures.includes(f)).map((feat) => {
                          const meta = AUDIO_FEATURE_META[feat];
                          return <FeatureBar key={feat} label={meta.label} value={audio[feat]} max={meta.max} unit={meta.unit} color={c.bar} />;
                        })}
                      </div>
                    </div>

                    {/* Tag weights */}
                    <div className="border-t border-white/5 pt-4">
                      <p className="text-[11px] text-brand-teal/50 uppercase tracking-wider font-semibold mb-3">Genre Weights</p>
                      <div className="space-y-1.5">
                        {Object.entries(cluster.centroid_features.tag_weights_top).slice(0, 6).map(([tag, weight]) => (
                          <div key={tag} className="flex items-center gap-2">
                            <span className="text-[11px] text-brand-teal/70 w-16 truncate">{tag}</span>
                            <div className="flex-1 h-1 rounded-full bg-white/5 overflow-hidden">
                              <div className={`h-full rounded-full ${c.bar} opacity-60`} style={{ width: `${(weight as number) * 500}%` }} />
                            </div>
                            <span className="text-[10px] font-mono text-brand-teal/40 w-10 text-right">{((weight as number) * 100).toFixed(1)}%</span>
                          </div>
                        ))}
                      </div>
                    </div>

                    {/* Sample tracks */}
                    {cluster.tracks.length > 0 && (
                      <div className="border-t border-white/5 pt-4">
                        <p className="text-[11px] text-brand-teal/50 uppercase tracking-wider font-semibold mb-3">
                          Sample Tracks <span className="text-brand-teal/30">({cluster.tracks.length})</span>
                        </p>
                        <div className="space-y-1">
                          {cluster.tracks.slice(0, 5).map((t) => (
                            <div key={t.spotify_id} className="flex items-center gap-2 py-1.5 px-2 rounded-lg hover:bg-white/[0.03] transition-colors">
                              <Music2 size={12} className="text-brand-teal/40 shrink-0" />
                              <span className="text-xs text-white truncate flex-1">{t.title}</span>
                              <span className="text-[10px] font-mono text-brand-teal/40">{(t.anomaly_score * 100).toFixed(0)}</span>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>

      {/* Anomalies */}
      {playlist.anomalies.length > 0 && (
        <AnomalySection anomalies={playlist.anomalies} />
      )}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Anomaly View — dedicated anomaly detection visualization
// ═══════════════════════════════════════════════════════════════════════════
function AnomalyView({ data }: { data: AnalysisResult }) {
  const [activePlaylist, setActivePlaylist] = useState(0);
  const playlist = data.playlists[activePlaylist];
  const anomalies = playlist.anomalies;

  // Group anomalies by cluster_id
  const byCluster = useMemo(() => {
    const map: Record<number, Anomaly[]> = {};
    anomalies.forEach((a) => {
      (map[a.cluster_id] ??= []).push(a);
    });
    return map;
  }, [anomalies]);

  // Score distribution buckets
  const buckets = useMemo(() => {
    const b = { severe: 0, moderate: 0, mild: 0 };
    anomalies.forEach((a) => {
      if (a.anomaly_score >= 0.9) b.severe++;
      else if (a.anomaly_score >= 0.85) b.moderate++;
      else b.mild++;
    });
    return b;
  }, [anomalies]);

  return (
    <div className="space-y-6 sm:space-y-10 animate-in fade-in duration-700">
      {/* Playlist tabs */}
      {data.playlists.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-2 -mb-2 scrollbar-none">
          {data.playlists.map((p, i) => (
            <button
              key={p.playlist_id}
              onClick={() => setActivePlaylist(i)}
              className={`shrink-0 px-4 py-2 rounded-xl text-sm font-medium transition-all duration-300 border ${
                i === activePlaylist
                  ? 'bg-red-500/15 border-red-500/40 text-red-400'
                  : 'bg-white/[0.02] border-white/5 text-brand-teal/60 hover:text-white hover:border-white/10'
              }`}
            >
              {p.playlist_name}
            </button>
          ))}
        </div>
      )}

      {/* Severity overview */}
      <div className="grid grid-cols-3 gap-2 sm:gap-4">
        <div className="bg-red-950/30 border border-red-500/20 p-3 sm:p-5 rounded-xl text-center">
          <div className="text-2xl sm:text-3xl font-black text-red-400">{buckets.severe}</div>
          <div className="text-[10px] sm:text-xs text-red-400/60 uppercase tracking-wider mt-1">Severe (&ge;90)</div>
        </div>
        <div className="bg-orange-950/20 border border-orange-500/20 p-3 sm:p-5 rounded-xl text-center">
          <div className="text-2xl sm:text-3xl font-black text-orange-400">{buckets.moderate}</div>
          <div className="text-[10px] sm:text-xs text-orange-400/60 uppercase tracking-wider mt-1">Moderate (85-89)</div>
        </div>
        <div className="bg-yellow-950/20 border border-yellow-500/20 p-3 sm:p-5 rounded-xl text-center">
          <div className="text-2xl sm:text-3xl font-black text-yellow-400">{buckets.mild}</div>
          <div className="text-[10px] sm:text-xs text-yellow-400/60 uppercase tracking-wider mt-1">Mild (&lt;85)</div>
        </div>
      </div>

      {/* Score cutoff info */}
      <div className="flex items-center gap-3 px-4 py-3 bg-white/[0.02] border border-white/5 rounded-xl">
        <AlertTriangle size={16} className="text-brand-teal/50 shrink-0" />
        <p className="text-xs text-brand-teal/60">
          Anomaly cutoff: <span className="text-white font-mono">{(playlist.summary.anomaly_score_cutoff * 100).toFixed(1)}</span> — tracks scoring above this threshold are flagged as outliers.
        </p>
      </div>

      {/* Anomaly breakdown by cluster */}
      <div>
        <h3 className="text-lg sm:text-xl font-bold text-white mb-4">By Cluster Origin</h3>
        <div className="space-y-3">
          {Object.entries(byCluster).map(([cid, items]) => (
            <div key={cid} className="bg-white/[0.02] border border-white/5 rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <span className="text-sm font-medium text-brand-teal/80">Cluster #{cid}</span>
                <Badge className="bg-red-500/15 text-red-400/80 border-0 text-[10px]">{items.length} outliers</Badge>
              </div>
              <div className="space-y-1.5">
                {items.slice(0, 5).map((a) => (
                  <AnomalyCard key={a.spotify_id} anomaly={a} />
                ))}
                {items.length > 5 && (
                  <p className="text-[11px] text-brand-teal/40 text-center pt-2">+{items.length - 5} more</p>
                )}
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Full ranked list */}
      <AnomalySection anomalies={anomalies} />
    </div>
  );
}

// ── Shared anomaly list section ──
function AnomalySection({ anomalies }: { anomalies: Anomaly[] }) {
  const [showAll, setShowAll] = useState(false);
  const visible = showAll ? anomalies : anomalies.slice(0, 8);

  return (
    <div>
      <h3 className="text-lg sm:text-xl font-bold text-red-400 mb-4 flex items-center gap-3">
        Ranked Outliers
        <Badge className="bg-red-500/15 text-red-400 border-0 text-xs">{anomalies.length}</Badge>
      </h3>
      <div className="space-y-2">
        {visible.map((a) => (
          <AnomalyCard key={a.spotify_id} anomaly={a} />
        ))}
      </div>
      {anomalies.length > 8 && (
        <button
          onClick={() => setShowAll(!showAll)}
          className="mt-3 text-xs text-brand-cyan hover:text-brand-cyan/80 transition-colors"
        >
          {showAll ? 'Show less' : `Show all ${anomalies.length} outliers`}
        </button>
      )}
    </div>
  );
}

// ── Summary metric card ──
function SummaryCard({ value, label, color, accent }: { value: number; label: string; color: string; accent?: boolean }) {
  return (
    <div className={`p-3 sm:p-5 rounded-xl text-center border ${accent ? 'bg-red-950/20 border-red-500/15 shadow-[0_0_20px_rgba(239,68,68,0.04)]' : 'bg-white/[0.02] border-white/10'}`}>
      <div className={`text-xl sm:text-3xl font-black ${color} mb-1`}>{value}</div>
      <div className="text-[10px] sm:text-xs text-brand-teal/50 uppercase tracking-wider">{label}</div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Recommendations View — track list grouped by source cluster
// ═══════════════════════════════════════════════════════════════════════════
function RecommendationsView({ data }: { data: EnrichedPlaylist }) {
  return (
    <div className="space-y-6 animate-in fade-in duration-700">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg sm:text-xl font-bold text-white">{data.name || 'Recommendations'}</h2>
          {data.description && <p className="text-sm text-brand-teal/60 mt-1">{data.description}</p>}
        </div>
        <Badge className="bg-brand-cyan/15 text-brand-cyan border-0 text-xs">{data.tracks.length} tracks</Badge>
      </div>

      <div className="space-y-2">
        {data.tracks.map((t, i) => (
          <div
            key={`${t.spotify_id}-${i}`}
            className="flex items-center gap-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-xl bg-white/[0.02] border border-white/5 hover:bg-white/[0.04] transition-colors group"
          >
            <div className="w-7 h-7 sm:w-8 sm:h-8 rounded-lg bg-brand-cyan/10 flex items-center justify-center shrink-0 text-brand-cyan text-[11px] font-bold">
              {i + 1}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate group-hover:text-brand-cyan transition-colors">{t.title}</p>
              <p className="text-xs text-brand-teal/50 truncate">
                {t.artists.map((a) => a.name).join(', ')} · {t.album_name}
              </p>
            </div>
            <span className="text-xs text-brand-teal/30 whitespace-nowrap hidden sm:inline font-mono">
              {Math.floor(t.duration_ms / 60000)}:{String(Math.floor((t.duration_ms % 60000) / 1000)).padStart(2, '0')}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Compare View — side-by-side playlist comparison
// ═══════════════════════════════════════════════════════════════════════════
function CompareView({ data }: { data: AnalysisResult }) {
  if (data.playlists.length < 2) {
    return <AnalysisView data={data} />;
  }

  const p1 = data.playlists[0];
  const p2 = data.playlists[1];

  // Compute average audio features per playlist
  function avgAudio(p: AnalysisPlaylist): AudioMeans {
    const clusters = Object.values(p.clusters);
    const total = clusters.reduce((s, c) => s + c.size, 0);
    const features = Object.keys(AUDIO_FEATURE_META) as (keyof AudioMeans)[];
    const avg: Partial<AudioMeans> = {};
    features.forEach((f) => {
      avg[f] = clusters.reduce((s, c) => s + c.centroid_features.audio_means[f] * c.size, 0) / total;
    });
    return avg as AudioMeans;
  }

  const avg1 = avgAudio(p1);
  const avg2 = avgAudio(p2);
  const features = Object.keys(AUDIO_FEATURE_META) as (keyof AudioMeans)[];

  // Shared clusters
  const clusters1 = new Set(Object.keys(p1.clusters));
  const clusters2 = new Set(Object.keys(p2.clusters));
  const shared = [...clusters1].filter((c) => clusters2.has(c));
  const unique1 = [...clusters1].filter((c) => !clusters2.has(c));
  const unique2 = [...clusters2].filter((c) => !clusters1.has(c));

  return (
    <div className="space-y-6 sm:space-y-10 animate-in fade-in duration-700">
      {/* Header row */}
      <div className="grid grid-cols-2 gap-3 sm:gap-6">
        <div className="bg-brand-cyan/5 border border-brand-cyan/20 p-4 sm:p-5 rounded-xl">
          <h3 className="text-sm sm:text-base font-bold text-brand-cyan truncate">{p1.playlist_name}</h3>
          <p className="text-xs text-brand-teal/50 mt-1">{p1.summary.num_eligible} tracks · {Object.keys(p1.clusters).length} clusters</p>
        </div>
        <div className="bg-brand-magenta/5 border border-brand-magenta/20 p-4 sm:p-5 rounded-xl">
          <h3 className="text-sm sm:text-base font-bold text-brand-magenta truncate">{p2.playlist_name}</h3>
          <p className="text-xs text-brand-teal/50 mt-1">{p2.summary.num_eligible} tracks · {Object.keys(p2.clusters).length} clusters</p>
        </div>
      </div>

      {/* Feature comparison */}
      <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 sm:p-6">
        <h4 className="text-sm font-semibold text-white mb-4">Audio Feature Comparison</h4>
        <div className="space-y-4">
          {features.map((feat) => {
            const meta = AUDIO_FEATURE_META[feat];
            const v1 = avg1[feat];
            const v2 = avg2[feat];
            const formatVal = meta.unit === '%' ? (v: number) => `${(v * 100).toFixed(0)}%`
              : meta.unit === 'BPM' ? (v: number) => `${v.toFixed(0)}`
              : (v: number) => `${v.toFixed(1)}`;
            const pct = (v: number) => meta.unit === 'dB'
              ? ((v - (-20)) / 20) * 100
              : meta.unit === 'BPM'
                ? ((v - 60) / 140) * 100
                : v * 100;
            return (
              <div key={feat}>
                <div className="flex justify-between text-[11px] mb-1.5">
                  <span className="text-brand-lavender/70">{meta.label}</span>
                  <div className="flex gap-3">
                    <span className="text-brand-cyan font-mono">{formatVal(v1)}</span>
                    <span className="text-brand-magenta font-mono">{formatVal(v2)}</span>
                  </div>
                </div>
                <div className="relative h-2 rounded-full bg-white/5 overflow-hidden">
                  <div className="absolute inset-y-0 left-0 bg-brand-cyan/60 rounded-full" style={{ width: `${Math.min(100, pct(v1))}%` }} />
                  <div className="absolute inset-y-0 left-0 bg-brand-magenta/40 rounded-full h-1 top-0.5" style={{ width: `${Math.min(100, pct(v2))}%` }} />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* Cluster overlap */}
      <div className="bg-white/[0.02] border border-white/5 rounded-xl p-4 sm:p-6">
        <h4 className="text-sm font-semibold text-white mb-4">Cluster Overlap</h4>
        <div className="space-y-3">
          {shared.length > 0 && (
            <div>
              <p className="text-[11px] text-green-400/70 uppercase tracking-wider font-semibold mb-2">Shared ({shared.length})</p>
              <div className="flex flex-wrap gap-2">
                {shared.map((c) => (
                  <Badge key={c} variant="outline" className="border-green-500/20 text-green-400/80 bg-green-500/5 capitalize text-xs">
                    {c.replace(/_/g, ' ')}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {unique1.length > 0 && (
            <div>
              <p className="text-[11px] text-brand-cyan/70 uppercase tracking-wider font-semibold mb-2">Only in {p1.playlist_name} ({unique1.length})</p>
              <div className="flex flex-wrap gap-2">
                {unique1.map((c) => (
                  <Badge key={c} variant="outline" className="border-brand-cyan/20 text-brand-cyan/80 bg-brand-cyan/5 capitalize text-xs">
                    {c.replace(/_/g, ' ')}
                  </Badge>
                ))}
              </div>
            </div>
          )}
          {unique2.length > 0 && (
            <div>
              <p className="text-[11px] text-brand-magenta/70 uppercase tracking-wider font-semibold mb-2">Only in {p2.playlist_name} ({unique2.length})</p>
              <div className="flex flex-wrap gap-2">
                {unique2.map((c) => (
                  <Badge key={c} variant="outline" className="border-brand-magenta/20 text-brand-magenta/80 bg-brand-magenta/5 capitalize text-xs">
                    {c.replace(/_/g, ' ')}
                  </Badge>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════
// Main ActionDashboard
// ═══════════════════════════════════════════════════════════════════════════

interface ActionDashboardProps {
  selectedPlaylists: Playlist[];
  currentAction: string;
  onNewAction: () => void;
}

export function ActionDashboard({ selectedPlaylists, currentAction, onNewAction }: ActionDashboardProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Record<string, unknown> | EnrichedPlaylist | null>(null);

  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const label = ACTION_LABELS[currentAction] ?? currentAction;

  // Mobile sidebar toggle
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // -----------------------------------------------------------------------
  // Save to Spotify
  // -----------------------------------------------------------------------
  const handleSaveToSpotify = useCallback(async () => {
    if (!result || !('tracks' in result) || !Array.isArray((result as EnrichedPlaylist).tracks)) return;
    setIsSaving(true);
    setSaveStatus('idle');
    try {
      await createPlaylist((result as EnrichedPlaylist).tracks);
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 3000);
    } catch (err) {
      console.error('Failed to save to Spotify', err);
      setSaveStatus('error');
    } finally {
      setIsSaving(false);
    }
  }, [result]);

  // -----------------------------------------------------------------------
  // Run the action once on mount
  // -----------------------------------------------------------------------
  const executeAction = useCallback(async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      switch (currentAction) {
        case 'analysis': {
          const data = await runAnalysis(selectedPlaylists);
          setResult(data);
          break;
        }
        case 'compare': {
          const analysisData = await runAnalysis(selectedPlaylists);
          if (selectedPlaylists.length > 0) {
            const cmp = await comparePlaylist(analysisData, selectedPlaylists[0]);
            setResult(cmp);
          } else {
            setResult(analysisData);
          }
          break;
        }
        case 'basic': {
          const analysisData = await runAnalysis(selectedPlaylists);
          const rec = await basicRecommendations(analysisData);
          setResult(rec);
          break;
        }
        case 'anomaly': {
          const analysisData = await runAnalysis(selectedPlaylists);
          const rec = await anomalyRecommendations(analysisData);
          setResult(rec);
          break;
        }
        default:
          setError(`Unknown action: ${currentAction}`);
      }
    } catch (err: unknown) {
      console.error('Action failed', err);
      setError(err instanceof Error ? err.message : 'Something went wrong');
    } finally {
      setLoading(false);
    }
  }, [currentAction, selectedPlaylists]);

  useEffect(() => {
    executeAction();
  }, [executeAction]);

  // -----------------------------------------------------------------------
  // Result renderer — dispatches to the correct view component
  // -----------------------------------------------------------------------
  function renderResult() {
    if (!result) return null;

    // Analysis view — check for playlists key (matches AnalysisResult shape)
    if ('playlists' in result && Array.isArray((result as any).playlists)) {
      const data = result as unknown as AnalysisResult;

      if (currentAction === 'anomaly') {
        return <AnomalyView data={data} />;
      }
      if (currentAction === 'compare') {
        return <CompareView data={data} />;
      }
      // Default: full analysis view
      return <AnalysisView data={data} />;
    }

    // EnrichedPlaylist view (recommendations / basic)
    if ('tracks' in result && Array.isArray((result as EnrichedPlaylist).tracks)) {
      return <RecommendationsView data={result as EnrichedPlaylist} />;
    }

    // Generic JSON fallback
    return (
      <pre className="text-xs text-brand-lavender/80 whitespace-pre-wrap break-words font-mono leading-relaxed">
        {JSON.stringify(result, null, 2)}
      </pre>
    );
  }

  // ── Sidebar content ──
  const sidebarContent = (
    <>
      <div className="p-6 lg:p-8 font-black text-xl lg:text-2xl border-b border-white/5 tracking-tighter text-white flex items-center justify-between">
        <span>OffBeat</span>
        <button onClick={() => setSidebarOpen(false)} className="lg:hidden p-1 -mr-1 text-brand-teal/60 hover:text-white transition-colors">
          <X size={20} />
        </button>
      </div>
      <div className="px-6 lg:px-8 py-4 lg:py-6 font-semibold text-xs text-brand-cyan uppercase tracking-[0.2em] opacity-80">Active Scope</div>

      <ScrollArea className="flex-1 px-3 lg:px-4">
        <div className="flex flex-col gap-1">
          {selectedPlaylists.map((p) => (
            <div key={p.spotify_id} className="px-3 lg:px-4 py-2.5 lg:py-3 text-sm font-medium rounded-xl text-white bg-white/[0.02] border border-white/5">
              <span className="block truncate">{p.name}</span>
              <span className="text-xs text-brand-teal/50">{p.total_tracks} tracks</span>
            </div>
          ))}
        </div>
      </ScrollArea>

      <div className="p-4 lg:p-6 border-t border-white/5">
        <Button
          variant="outline"
          onClick={handleSaveToSpotify}
          disabled={isSaving || !result || !('tracks' in result)}
          className={`w-full h-10 lg:h-12 rounded-xl text-sm text-white transition-all duration-300 ${
            saveStatus === 'success' ? 'bg-green-500/20 border-green-500/50 text-green-400 hover:bg-green-500/30' :
            saveStatus === 'error' ? 'bg-red-500/20 border-red-500/50 text-red-400 hover:bg-red-500/30' :
            'border-white/10 hover:bg-white/5 hover:text-white bg-transparent'
          }`}
        >
          {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
          {saveStatus === 'success' ? 'Saved!' :
           saveStatus === 'error' ? 'Failed' :
           'Create Playlist'}
        </Button>
      </div>
    </>
  );

  return (
    <div className="flex h-[100dvh] bg-gray-950 text-brand-lavender selection:bg-brand-cyan/30">
      {/* ── Mobile backdrop ── */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-30 lg:hidden animate-in fade-in duration-200"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ── */}
      <div className={`
        fixed inset-y-0 left-0 z-40 w-72 lg:w-80
        border-r border-white/5 bg-gray-950/95 backdrop-blur-xl shadow-2xl
        flex flex-col
        transition-transform duration-300 ease-out
        lg:relative lg:translate-x-0 lg:z-20
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        {sidebarContent}
      </div>

      {/* ── Main content ── */}
      <div className="flex-1 flex flex-col relative bg-gray-950 min-w-0">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom_right,_var(--tw-gradient-stops))] from-brand-indigo/10 via-gray-950 to-gray-950 pointer-events-none" />

        {/* Header */}
        <div className="flex items-center justify-between px-4 sm:px-6 lg:px-10 py-4 sm:py-6 lg:py-8 z-10 gap-3">
          <div className="flex items-center gap-3 sm:gap-5 min-w-0">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 -ml-2 rounded-xl text-brand-teal/70 hover:text-white hover:bg-white/5 transition-colors shrink-0"
            >
              <Menu size={22} />
            </button>
            <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold tracking-tight text-white truncate">{label}</h1>
            <div className={`px-2 sm:px-3 py-1 sm:py-1.5 rounded-lg text-[10px] sm:text-xs font-bold uppercase tracking-wider sm:tracking-widest border shrink-0 ${
              loading
                ? 'bg-brand-cyan/10 text-brand-cyan border-brand-cyan/20'
                : error
                  ? 'bg-red-500/10 text-red-400 border-red-400/20'
                  : 'bg-green-500/10 text-green-400 border-green-400/20'
            }`}>
              {loading ? 'Processing' : error ? 'Error' : 'Complete'}
            </div>
          </div>
          <Button onClick={onNewAction} variant="ghost" className="text-brand-teal/70 hover:text-white hover:bg-white/5 rounded-xl px-3 sm:px-6 text-sm shrink-0">
            <span className="hidden sm:inline">Back to Actions</span>
            <span className="sm:hidden">Back</span>
          </Button>
        </div>

        {/* Data Visualization Area */}
        <div className="flex-1 px-3 sm:px-6 lg:px-10 pb-24 sm:pb-28 lg:pb-32 relative z-10 flex flex-col overflow-hidden">
          <div className="w-full flex-1 border border-white/5 rounded-2xl sm:rounded-3xl flex flex-col items-center justify-center text-brand-teal bg-white/[0.01] relative overflow-hidden shadow-2xl backdrop-blur-sm">
            {/* Subtle aesthetic grid */}
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff03_1px,transparent_1px),linear-gradient(to_bottom,#ffffff03_1px,transparent_1px)] bg-[size:32px_32px]" />

            {loading && (
              <div className="relative z-10 flex flex-col items-center px-4">
                <Loader2 className="w-10 h-10 sm:w-12 sm:h-12 animate-spin text-brand-cyan mb-4 sm:mb-6" />
                <p className="font-mono text-xs sm:text-sm tracking-widest text-brand-lavender/60 text-center">
                  RUNNING {currentAction.toUpperCase()}…
                </p>
              </div>
            )}

            {error && !loading && (
              <div className="relative z-10 flex flex-col items-center text-center max-w-md px-6">
                <AlertTriangle className="w-10 h-10 sm:w-12 sm:h-12 text-red-400 mb-4" />
                <p className="text-red-400 font-medium mb-2">Action failed</p>
                <p className="text-sm text-brand-teal/60">{error}</p>
                <Button
                  onClick={executeAction}
                  className="mt-6 bg-brand-cyan hover:bg-[#008be5] text-white rounded-xl"
                >
                  Retry
                </Button>
              </div>
            )}

            {!loading && !error && result && (
              <ScrollArea className="absolute inset-0 p-4 sm:p-6 lg:p-8">
                {renderResult()}
              </ScrollArea>
            )}
          </div>
        </div>

        {/* Floating Chat Pill */}
        <div className="absolute bottom-3 sm:bottom-6 lg:bottom-8 left-1/2 -translate-x-1/2 w-full max-w-3xl z-30 px-3 sm:px-6">
          <div className="flex gap-2 bg-gray-900/80 p-1.5 sm:p-2 rounded-xl sm:rounded-2xl border border-white/10 backdrop-blur-xl shadow-[0_10px_40px_rgba(0,0,0,0.5)]">
            <Input
              placeholder="Ask SphinxAI…"
              className="flex-1 h-10 sm:h-12 border-0 bg-transparent text-white placeholder:text-brand-teal/40 focus-visible:ring-0 text-sm sm:text-base px-3 sm:px-6"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  console.log("Sending to Sphinx FastAPI:", e.currentTarget.value);
                  e.currentTarget.value = "";
                }
              }}
            />
            <Button className="h-10 w-10 sm:h-12 sm:w-12 rounded-lg sm:rounded-xl bg-brand-cyan hover:bg-[#008be5] text-white shadow-[0_0_15px_rgba(0,158,250,0.3)] transition-all duration-300 p-0 flex items-center justify-center shrink-0">
              <ArrowRight size={18} />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}