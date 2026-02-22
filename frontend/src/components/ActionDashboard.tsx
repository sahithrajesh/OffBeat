import { useState, useEffect, useCallback } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { ArrowRight, Loader2, AlertTriangle } from 'lucide-react';
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
  currentAction: string;          // action key: "analysis" | "compare" | "basic" | "anomaly"
  onNewAction: () => void;
}

export function ActionDashboard({ selectedPlaylists, currentAction, onNewAction }: ActionDashboardProps) {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  // Generic result bucket — shape depends on the endpoint.
  const [result, setResult] = useState<Record<string, unknown> | EnrichedPlaylist | null>(null);

  const [isSaving, setIsSaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState<'idle' | 'success' | 'error'>('idle');
  const label = ACTION_LABELS[currentAction] ?? currentAction;

  // -----------------------------------------------------------------------
  // Handle saving to Spotify
  // -----------------------------------------------------------------------
  const handleSaveToSpotify = useCallback(async () => {
    // Ensure we actually have track data to save
    if (!result || !('tracks' in result) || !Array.isArray((result as EnrichedPlaylist).tracks)) return;
    
    setIsSaving(true);
    setSaveStatus('idle');
    
    try {
      await createPlaylist((result as EnrichedPlaylist).tracks);
      setSaveStatus('success');
      setTimeout(() => setSaveStatus('idle'), 3000); // Reset button after 3s
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
          // Run analysis first, then compare each playlist against it.
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
  // Result renderer — adapts to the shape of data returned
  // -----------------------------------------------------------------------
  function renderResult() {
    if (!result) return null;

    // If the result looks like an EnrichedPlaylist (has `tracks` array)
    if ('tracks' in result && Array.isArray((result as EnrichedPlaylist).tracks)) {
      const ep = result as EnrichedPlaylist;
      return (
        <div className="space-y-4">
          <h2 className="text-xl font-semibold text-white">{ep.name}</h2>
          {ep.description && <p className="text-sm text-brand-teal/70">{ep.description}</p>}
          <p className="text-xs text-brand-teal/50">{ep.tracks.length} tracks</p>

          <div className="space-y-2 mt-4">
            {ep.tracks.map((t) => (
              <div
                key={t.spotify_id}
                className="flex items-center gap-3 px-4 py-3 rounded-xl bg-white/[0.02] border border-white/5"
              >
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-medium text-white truncate">{t.title}</p>
                  <p className="text-xs text-brand-teal/60 truncate">
                    {t.artists.map((a) => a.name).join(', ')} · {t.album_name}
                  </p>
                </div>
                <span className="text-xs text-brand-teal/40 whitespace-nowrap">
                  {Math.floor(t.duration_ms / 60000)}:{String(Math.floor((t.duration_ms % 60000) / 1000)).padStart(2, '0')}
                </span>
              </div>
            ))}
          </div>
        </div>
      );
    }

    // Generic JSON display for analysis / compare results
    return (
      <pre className="text-xs text-brand-lavender/80 whitespace-pre-wrap break-words font-mono leading-relaxed">
        {JSON.stringify(result, null, 2)}
      </pre>
    );
  }

  return (
    <div className="flex h-screen bg-gray-950 text-brand-lavender selection:bg-brand-cyan/30">
      {/* Left Sidebar */}
      <div className="w-80 shrink-0 border-r border-white/5 bg-gray-950/80 flex flex-col z-20 backdrop-blur-xl shadow-2xl">
        <div className="p-8 font-black text-2xl border-b border-white/5 tracking-tighter text-white">OffBeat</div>
        <div className="px-8 py-6 font-semibold text-xs text-brand-cyan uppercase tracking-[0.2em] opacity-80">Active Scope</div>
        
        <ScrollArea className="flex-1 px-4">
          <div className="flex flex-col gap-1">
            {selectedPlaylists.map((p) => (
              <div key={p.spotify_id} className="px-4 py-3 text-sm font-medium rounded-xl text-white bg-white/[0.02] border border-white/5">
                <span className="block truncate">{p.name}</span>
                <span className="text-xs text-brand-teal/50">{p.total_tracks} tracks</span>
              </div>
            ))}
          </div>
        </ScrollArea>
        
        <div className="p-6 border-t border-white/5">
           <Button 
             variant="outline" 
             onClick={handleSaveToSpotify}
             disabled={isSaving || !result || !('tracks' in result)}
             className={`w-full h-12 rounded-xl text-white transition-all duration-300 ${
               saveStatus === 'success' ? 'bg-green-500/20 border-green-500/50 text-green-400 hover:bg-green-500/30' :
               saveStatus === 'error' ? 'bg-red-500/20 border-red-500/50 text-red-400 hover:bg-red-500/30' :
               'border-white/10 hover:bg-white/5 hover:text-white bg-transparent'
             }`}
           >
             {isSaving ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : null}
             {saveStatus === 'success' ? 'Saved to Library!' : 
              saveStatus === 'error' ? 'Failed to Create' : 
              'Create Playlist'}
           </Button>
        </div>
      </div>

      {/* Main Content & Chat Area */}
      <div className="flex-1 flex flex-col relative bg-gray-950">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_bottom_right,_var(--tw-gradient-stops))] from-brand-indigo/10 via-gray-950 to-gray-950 pointer-events-none"></div>
        
        {/* Header */}
        <div className="flex items-center justify-between px-10 py-8 z-10">
          <div className="flex items-center gap-5">
            <h1 className="text-3xl font-bold tracking-tight text-white">{label}</h1>
            <div className={`px-3 py-1.5 rounded-lg text-xs font-bold uppercase tracking-widest border ${
              loading
                ? 'bg-brand-cyan/10 text-brand-cyan border-brand-cyan/20'
                : error
                  ? 'bg-red-500/10 text-red-400 border-red-400/20'
                  : 'bg-green-500/10 text-green-400 border-green-400/20'
            }`}>
              {loading ? 'Processing' : error ? 'Error' : 'Complete'}
            </div>
          </div>
          <Button onClick={onNewAction} variant="ghost" className="text-brand-teal/70 hover:text-white hover:bg-white/5 rounded-xl px-6">
            Back to Actions
          </Button>
        </div>

        {/* Data Visualization Area */}
        <div className="flex-1 px-10 pb-32 relative z-10 flex flex-col overflow-hidden">
          <div className="w-full flex-1 border border-white/5 rounded-3xl flex flex-col items-center justify-center text-brand-teal bg-white/[0.01] relative overflow-hidden shadow-2xl backdrop-blur-sm">
            {/* Subtle aesthetic grid */}
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#ffffff03_1px,transparent_1px),linear-gradient(to_bottom,#ffffff03_1px,transparent_1px)] bg-[size:32px_32px]"></div>

            {loading && (
              <div className="relative z-10 flex flex-col items-center">
                <Loader2 className="w-12 h-12 animate-spin text-brand-cyan mb-6" />
                <p className="font-mono text-sm tracking-widest text-brand-lavender/60">
                  RUNNING {currentAction.toUpperCase()}…
                </p>
              </div>
            )}

            {error && !loading && (
              <div className="relative z-10 flex flex-col items-center text-center max-w-md">
                <AlertTriangle className="w-12 h-12 text-red-400 mb-4" />
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
              <ScrollArea className="absolute inset-0 p-8">
                {renderResult()}
              </ScrollArea>
            )}
          </div>
        </div>

        {/* Floating Chat Pill */}
        <div className="absolute bottom-8 left-1/2 -translate-x-1/2 w-full max-w-3xl z-30 px-6">
          <div className="flex gap-2 bg-gray-900/80 p-2 rounded-2xl border border-white/10 backdrop-blur-xl shadow-[0_10px_40px_rgba(0,0,0,0.5)]">
            <Input 
              placeholder="Ask SphinxAI to slice the data differently..." 
              className="flex-1 h-12 border-0 bg-transparent text-white placeholder:text-brand-teal/40 focus-visible:ring-0 text-base px-6"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  console.log("Sending to Sphinx FastAPI:", e.currentTarget.value);
                  e.currentTarget.value = ""; 
                }
              }}
            />
            <Button className="h-12 w-12 rounded-xl bg-brand-cyan hover:bg-[#008be5] text-white shadow-[0_0_15px_rgba(0,158,250,0.3)] transition-all duration-300 p-0 flex items-center justify-center">
              <ArrowRight size={20} />
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}