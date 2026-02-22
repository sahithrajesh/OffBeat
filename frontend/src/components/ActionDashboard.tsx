import { useState, useEffect, useCallback, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import { Badge } from '@/components/ui/badge';
import { ArrowRight, Loader2, AlertTriangle, Menu, X } from 'lucide-react';
import type { Playlist, EnrichedPlaylist } from '@/lib/api';
import {
  runAnalysis,
  comparePlaylist,
  basicRecommendations,
  anomalyRecommendations,
  createPlaylist,
} from '@/lib/api';

/** Human-readable labels for backend action keys */
const ACTION_LABELS: Record<string, string> = {
  analysis: 'Playlist Analysis',
  compare: 'Playlist Comparisons',
  basic: 'Recommendations',
  anomaly: 'Anomaly Detection',
};

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

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playingTrackId, setPlayingTrackId] = useState<string | null>(null);

  // Mobile sidebar toggle
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // -----------------------------------------------------------------------
  // Audio preview
  // -----------------------------------------------------------------------
  const togglePreview = (trackId: string, previewUrl: string) => {
    if (!audioRef.current) {
      audioRef.current = new Audio(previewUrl);
    }
    if (playingTrackId === trackId) {
      audioRef.current.pause();
      setPlayingTrackId(null);
      return;
    }
    audioRef.current.src = previewUrl;
    audioRef.current.play();
    setPlayingTrackId(trackId);
  };

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
  // Result renderer
  // -----------------------------------------------------------------------
  function renderResult() {
    if (!result) return null;

    // EnrichedPlaylist view
    if ('tracks' in result && Array.isArray((result as EnrichedPlaylist).tracks)) {
      const ep = result as EnrichedPlaylist;
      return (
        <div className="space-y-4">
          <h2 className="text-lg sm:text-xl font-semibold text-white">{ep.name}</h2>
          {ep.description && <p className="text-sm text-brand-teal/70">{ep.description}</p>}
          <p className="text-xs text-brand-teal/50">{ep.tracks.length} tracks</p>

          <div className="space-y-2 mt-4">
            {ep.tracks.map((t: any) => (
              <div
                key={t.spotify_id}
                className="flex items-center gap-3 px-3 sm:px-4 py-2.5 sm:py-3 rounded-xl bg-white/[0.02] border border-white/5"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{t.title}</p>
                  <p className="text-xs text-brand-teal/60 truncate">
                    {t.artists.map((a) => a.name).join(', ')} · {t.album_name}
                  </p>
                </div>
                <span className="text-xs text-brand-teal/40 whitespace-nowrap hidden sm:inline">
                  {Math.floor(t.duration_ms / 60000)}:{String(Math.floor((t.duration_ms % 60000) / 1000)).padStart(2, '0')}
                </span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Analysis view
    if (currentAction === 'analysis' && result && 'playlists' in result) {
      const analysisData = result as any;
      const playlistData = analysisData.playlists[0];

      return (
        <div className="space-y-8 sm:space-y-12 animate-in fade-in duration-700">

          {/* 1. Summary Metrics */}
          <div className="grid grid-cols-3 gap-2 sm:gap-6">
            <div className="bg-white/[0.02] border border-white/10 p-3 sm:p-6 rounded-xl sm:rounded-2xl text-center">
              <div className="text-xl sm:text-4xl font-black text-brand-cyan mb-1 sm:mb-2">{playlistData.summary.num_eligible}</div>
              <div className="text-[10px] sm:text-xs text-brand-teal/60 uppercase tracking-wider sm:tracking-widest">Analyzed</div>
            </div>
            <div className="bg-white/[0.02] border border-white/10 p-3 sm:p-6 rounded-xl sm:rounded-2xl text-center">
              <div className="text-xl sm:text-4xl font-black text-brand-magenta mb-1 sm:mb-2">{playlistData.summary.num_clusters}</div>
              <div className="text-[10px] sm:text-xs text-brand-teal/60 uppercase tracking-wider sm:tracking-widest">Personas</div>
            </div>
            <div className="bg-white/[0.02] border border-red-500/20 p-3 sm:p-6 rounded-xl sm:rounded-2xl text-center shadow-[0_0_30px_rgba(239,68,68,0.05)]">
              <div className="text-xl sm:text-4xl font-black text-red-400 mb-1 sm:mb-2">{playlistData.summary.num_anomalies}</div>
              <div className="text-[10px] sm:text-xs text-brand-teal/60 uppercase tracking-wider sm:tracking-widest">Outliers</div>
            </div>
          </div>

          {/* 2. Cluster Breakdown */}
          <div>
            <h3 className="text-xl sm:text-2xl font-bold text-white mb-4 sm:mb-6">Playlist DNA</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-6">
              {Object.entries(playlistData.clusters).map(([clusterName, cluster]: [string, any], idx: number) => (
                <div key={idx} className="bg-white/[0.02] border border-white/5 p-4 sm:p-6 rounded-xl sm:rounded-2xl">
                  <h4 className="text-sm sm:text-lg font-bold text-white capitalize mb-3 sm:mb-4">
                    {clusterName.replace(/_/g, ' ')}
                    <span className="text-xs font-normal text-brand-teal/50 ml-2 sm:ml-3">({cluster.size} tracks)</span>
                  </h4>

                  {/* Audio Feature Bars */}
                  <div className="space-y-3 sm:space-y-4 mb-4 sm:mb-6">
                    <div>
                      <div className="flex justify-between text-xs mb-1.5"><span className="text-brand-lavender/80">Energy</span><span className="text-brand-cyan">{(cluster.centroid_features.audio_means.energy * 100).toFixed(0)}%</span></div>
                      <Progress value={cluster.centroid_features.audio_means.energy * 100} className="h-1.5 bg-white/5" />
                    </div>
                    <div>
                      <div className="flex justify-between text-xs mb-1.5"><span className="text-brand-lavender/80">Danceability</span><span className="text-brand-magenta">{(cluster.centroid_features.audio_means.danceability * 100).toFixed(0)}%</span></div>
                      <Progress value={cluster.centroid_features.audio_means.danceability * 100} className="h-1.5 bg-white/5" />
                    </div>
                  </div>

                  {/* Tag Cloud */}
                  <div className="flex flex-wrap gap-1.5 sm:gap-2">
                    {cluster.centroid_features.top_tags.slice(0, 5).map((tag: string) => (
                      <Badge key={tag} variant="outline" className="border-white/10 text-brand-teal/80 bg-black/20 text-[10px] sm:text-xs">{tag}</Badge>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* 3. Anomalies List */}
          <div>
            <h3 className="text-xl sm:text-2xl font-bold text-red-400 mb-4 sm:mb-6 flex items-center gap-3">
              Outliers <Badge className="bg-red-500/20 text-red-400 border-0">{playlistData.anomalies.length}</Badge>
            </h3>
            <div className="space-y-2 sm:space-y-3">
              {playlistData.anomalies.slice(0, 10).map((anomaly: any) => (
                <div key={anomaly.spotify_id} className="p-3 sm:p-4 rounded-xl bg-red-950/20 border border-red-500/20 flex gap-3 sm:gap-4 items-center">
                  <div className="w-10 h-10 sm:w-12 sm:h-12 rounded-lg bg-red-500/10 flex items-center justify-center shrink-0 text-red-400 font-mono text-xs">
                    {(anomaly.anomaly_score * 100).toFixed(0)}
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm sm:text-base text-white font-medium truncate">{anomaly.title}</div>
                    <div className="text-xs text-red-300/70 mt-0.5 sm:mt-1 line-clamp-1">{anomaly.reason}</div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      );
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