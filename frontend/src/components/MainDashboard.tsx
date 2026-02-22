import { useState, useEffect } from 'react';
import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Disc3, Check, AlertCircle } from 'lucide-react';
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
    { title: "Anomaly Detection",     key: "anomaly", desc: "Find songs that don't belong in these playlists." },
    { title: "Playlist Analysis",     key: "analysis", desc: "Run Sphinx AI analysis on your selected playlists." },
    { title: "Playlist Comparisons",  key: "compare",  desc: "See the overlap and differences between selections." },
    { title: "Recommendations",       key: "basic",    desc: "Get AI suggestions to improve your mixes." },
  ];

  const hasSelection = selectedPlaylists.length > 0;

  // State for user profile
  const [user, setUser] = useState<{ display_name: string } | null>(null);

  useEffect(() => {
    // Only call /auth/me if we actually have a token.
    if (!getToken()) return;
    fetchMe()
      .then((profile) => setUser(profile))
      .catch(() => setUser(null)); // silently fail — cosmetic only
  }, []);

  return (
    <div className="flex h-screen bg-gray-950 text-brand-lavender selection:bg-brand-cyan/30 font-sans tracking-wide">
      {/* Left Sidebar */}
      <div className="w-80 shrink-0 border-r border-white/5 bg-gray-950/80 flex flex-col z-20 backdrop-blur-xl shadow-2xl">
        <div className="p-8 font-black text-2xl border-b border-white/5 tracking-tighter text-white">OffBeat</div>
        <div className="px-8 py-6 font-semibold text-xs text-brand-teal uppercase tracking-[0.2em] opacity-80">Your Library</div>
        <ScrollArea className="flex-1 px-4">
          <div className="flex flex-col gap-1.5 pb-4">
            {playlists.map((p) => {
              const isSelected = selectedPlaylists.includes(p.spotify_id);
              return (
                <button 
                  key={p.spotify_id}
                  onClick={() => togglePlaylist(p.spotify_id)}
                  className={`relative flex items-center gap-4 p-3 rounded-2xl transition-all duration-500 ease-out text-left w-full border outline-none focus-visible:ring-1 focus-visible:ring-brand-magenta/50 ${
                    isSelected 
                      ? 'bg-brand-plum/10 border-brand-magenta/30 shadow-[0_4px_20px_rgba(123,61,135,0.15)]' 
                      : 'bg-transparent border-transparent hover:bg-white/[0.03]'
                  }`}
                >
                  {p.image_url ? (
                    <img
                      src={p.image_url}
                      alt={p.name}
                      className={`w-11 h-11 rounded-xl shrink-0 object-cover transition-all duration-500 border ${
                        isSelected ? 'border-brand-magenta/30' : 'border-transparent'
                      }`}
                    />
                  ) : (
                    <div className={`flex items-center justify-center w-11 h-11 rounded-xl shrink-0 transition-all duration-500 ${
                      isSelected ? 'bg-brand-magenta/20 text-brand-magenta border border-brand-magenta/30' : 'bg-white/[0.03] text-brand-teal/60 border border-transparent'
                    }`}>
                      <Disc3 size={20} strokeWidth={1.5} />
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
                  <div className="shrink-0 pr-2">
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
        <div className="p-6 border-t border-white/5 bg-gray-950 text-xs font-medium text-brand-teal/50">
          {user ? `@${user.display_name}` : '@…'}
        </div>
      </div>
      {/* Main Actions Area */}
      <div className="flex-1 p-12 overflow-y-auto bg-gray-950 relative">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,_var(--tw-gradient-stops))] from-brand-indigo/10 via-gray-950 to-gray-950 pointer-events-none"></div>
        <div className="relative z-10 max-w-5xl mx-auto pt-8">
          <h1 className="text-4xl font-bold mb-3 tracking-tight text-white">Select Action</h1>
          {/* Warning Message */}
          <div className={`flex items-center gap-2 mb-10 transition-all duration-500 ${hasSelection ? 'opacity-0 -translate-y-2' : 'opacity-100 translate-y-0 text-brand-magenta/80'}`}>
            <AlertCircle size={16} />
            <p className="text-sm font-medium">Select a playlist from your library to begin analysis.</p>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
            {actions.map((action) => (
              <Card 
                key={action.key}
                className={`p-8 rounded-2xl transition-all duration-500 ease-out backdrop-blur-sm ${
                  hasSelection 
                    ? 'cursor-pointer bg-white/[0.02] border-white/5 hover:bg-white/[0.04] hover:border-brand-cyan/40 hover:shadow-[0_8px_30px_rgba(0,158,250,0.12)] hover:-translate-y-1 group' 
                    : 'cursor-not-allowed opacity-30 bg-white/[0.01] border-white/5'
                }`}
                onClick={() => hasSelection && onActionSelect(action.key)}
              >
                <h3 className={`font-semibold text-xl transition-colors duration-500 ${hasSelection ? 'text-white group-hover:text-brand-cyan' : 'text-gray-500'}`}>
                  {action.title}
                </h3>
                <p className={`text-sm mt-3 leading-relaxed transition-colors duration-500 ${hasSelection ? 'text-brand-teal/70' : 'text-gray-600'}`}>
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