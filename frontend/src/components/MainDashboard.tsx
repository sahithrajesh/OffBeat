import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Disc3, Check, AlertCircle, Menu, X } from 'lucide-react';
import type { Playlist } from '@/lib/api';
import { fetchMe } from '@/lib/api';
import { getToken } from '@/lib/auth';

interface MainDashboardProps {
  playlists: Playlist[];
  selectedPlaylists: string[];
  togglePlaylist: (id: string) => void;
  onActionSelect: (action: string) => void;
}

export function MainDashboard({ playlists, selectedPlaylists, togglePlaylist, onActionSelect }: MainDashboardProps) {
  const actions = [
    { key: "anomaly", title: "Anomaly Detection", desc: "Find songs that don't belong in these playlists." },
    { key: "analysis", title: "Mood Detection", desc: "Analyze the acoustic sentiment of your tracks." },
    { key: "compare", title: "Playlist Comparisons", desc: "See the overlap and differences between selections." },
    { key: "basic", title: "Mood Finder", desc: "Generate a new playlist based on a specific vibe." },
    { key: "recommendations", title: "Recommendations", desc: "Get AI suggestions to improve your mixes." }
  ];

  const hasSelection = selectedPlaylists.length > 0;

  // Mobile sidebar toggle
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // State for user profile
  const [user, setUser] = useState<{ display_name: string } | null>(null);

  useEffect(() => {
    if (!getToken()) return;
    fetchMe()
      .then((profile: any) => setUser(profile))
      .catch(() => setUser(null));
  }, []);

  // Close sidebar when a playlist is toggled on mobile
  const handleTogglePlaylist = (id: string) => {
    togglePlaylist(id);
  };

  // ── Sidebar content (shared between mobile drawer & desktop panel) ──
  const sidebarContent = (
    <>
      <div className="p-6 lg:p-8 font-black text-xl lg:text-2xl border-b border-white/5 tracking-tighter text-white flex items-center justify-between">
        <span>OffBeat</span>
        {/* Close button — mobile only */}
        <button onClick={() => setSidebarOpen(false)} className="lg:hidden p-1 -mr-1 text-brand-teal/60 hover:text-white transition-colors">
          <X size={20} />
        </button>
      </div>
      <div className="px-6 lg:px-8 py-4 lg:py-6 font-semibold text-xs text-brand-teal uppercase tracking-[0.2em] opacity-80">Your Library</div>
      <ScrollArea className="flex-1 px-3 lg:px-4">
        <div className="flex flex-col gap-1 pb-4">
          {playlists.map((p) => {
            const isSelected = selectedPlaylists.includes(p.spotify_id);
            return (
              <button
                key={p.spotify_id}
                onClick={() => handleTogglePlaylist(p.spotify_id)}
                className={`relative flex items-center gap-3 p-2.5 lg:p-3 rounded-xl lg:rounded-2xl transition-all duration-500 ease-out text-left w-full border outline-none focus-visible:ring-1 focus-visible:ring-brand-magenta/50 ${
                  isSelected
                    ? 'bg-brand-plum/10 border-brand-magenta/30 shadow-[0_4px_20px_rgba(123,61,135,0.15)]'
                    : 'bg-transparent border-transparent hover:bg-white/[0.03]'
                }`}
              >
                {p.image_url ? (
                  <img
                    src={p.image_url}
                    alt={p.name}
                    className={`w-9 h-9 lg:w-11 lg:h-11 rounded-lg lg:rounded-xl shrink-0 object-cover transition-all duration-500 border ${
                      isSelected ? 'border-brand-magenta/30' : 'border-transparent'
                    }`}
                  />
                ) : (
                  <div className={`flex items-center justify-center w-9 h-9 lg:w-11 lg:h-11 rounded-lg lg:rounded-xl shrink-0 transition-all duration-500 ${
                    isSelected ? 'bg-brand-magenta/20 text-brand-magenta border border-brand-magenta/30' : 'bg-white/[0.03] text-brand-teal/60 border border-transparent'
                  }`}>
                    <Disc3 size={18} strokeWidth={1.5} />
                  </div>
                )}
                <div className="flex-1 overflow-hidden">
                  <h4 className={`text-sm font-medium truncate transition-colors duration-500 ${
                    isSelected ? 'text-white' : 'text-brand-lavender/80'
                  }`}>
                    {p.name}
                  </h4>
                  <p className="text-xs text-brand-teal/50 truncate">{p.total_tracks} tracks · {p.owner}</p>
                </div>
                <div className="shrink-0 pr-1 lg:pr-2">
                  <div className={`w-5 h-5 rounded-full border flex items-center justify-center transition-all duration-500 ${
                    isSelected ? 'border-brand-magenta bg-brand-magenta text-white scale-100 shadow-[0_0_10px_rgba(123,61,135,0.5)]' : 'border-white/10 bg-transparent scale-75 opacity-0'
                  }`}>
                    {isSelected && <Check size={12} strokeWidth={4} />}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      </ScrollArea>
      <div className="p-4 lg:p-6 border-t border-white/5 bg-gray-950 text-xs font-medium text-brand-teal/50">
        {user ? `@${user.display_name}` : '@…'}
      </div>
    </>
  );

  return (
    <div className="flex h-[100dvh] bg-gray-950 text-brand-lavender selection:bg-brand-cyan/30 font-sans tracking-wide">
      {/* ── Mobile: backdrop overlay ── */}
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
      <div className="flex-1 overflow-y-auto bg-gray-950 relative min-w-0">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_var(--tw-gradient-stops))] from-brand-indigo/10 via-gray-950 to-gray-950 pointer-events-none" />

        <div className="relative z-10 max-w-5xl mx-auto px-4 sm:px-8 lg:px-12 pt-4 sm:pt-8 pb-8">
          {/* Mobile header bar */}
          <div className="flex items-center gap-3 mb-6 lg:mb-0">
            <button
              onClick={() => setSidebarOpen(true)}
              className="lg:hidden p-2 -ml-2 rounded-xl text-brand-teal/70 hover:text-white hover:bg-white/5 transition-colors"
            >
              <Menu size={22} />
            </button>
            <h1 className="text-2xl sm:text-3xl lg:text-4xl font-bold tracking-tight text-white">Select Action</h1>
            {/* Selection count badge — mobile */}
            {hasSelection && (
              <span className="lg:hidden ml-auto text-xs font-bold text-brand-magenta bg-brand-magenta/10 border border-brand-magenta/30 px-2.5 py-1 rounded-full">
                {selectedPlaylists.length} selected
              </span>
            )}
          </div>

          {/* Warning */}
          <div className={`flex items-center gap-2 mb-6 lg:mb-10 transition-all duration-500 ${hasSelection ? 'opacity-0 -translate-y-2 h-0 overflow-hidden' : 'opacity-100 translate-y-0 text-brand-magenta/80'}`}>
            <AlertCircle size={16} className="shrink-0" />
            <p className="text-sm font-medium">Select a playlist from your library to begin analysis.</p>
          </div>

          {/* Action cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 sm:gap-5">
            {actions.map((action) => (
              <Card
                key={action.key}
                className={`p-5 sm:p-8 rounded-xl sm:rounded-2xl transition-all duration-500 ease-out backdrop-blur-sm ${
                  hasSelection
                    ? 'cursor-pointer bg-white/[0.02] border-white/5 hover:bg-white/[0.04] hover:border-brand-cyan/40 hover:shadow-[0_8px_30px_rgba(0,158,250,0.12)] hover:-translate-y-1 active:translate-y-0 group'
                    : 'cursor-not-allowed opacity-30 bg-white/[0.01] border-white/5'
                }`}
                onClick={() => hasSelection && onActionSelect(action.key)}
              >
                <h3 className={`font-semibold text-base sm:text-xl transition-colors duration-500 ${hasSelection ? 'text-white group-hover:text-brand-cyan' : 'text-gray-500'}`}>
                  {action.title}
                </h3>
                <p className={`text-xs sm:text-sm mt-2 sm:mt-3 leading-relaxed transition-colors duration-500 ${hasSelection ? 'text-brand-teal/70' : 'text-gray-600'}`}>
                  {action.desc}
                </p>
              </Card>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}