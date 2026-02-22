import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Disc3, Check } from 'lucide-react';
import { Playlist } from '../App';

interface MainDashboardProps {
  playlists: Playlist[];
  selectedPlaylists: string[];
  togglePlaylist: (id: string) => void;
  onActionSelect: (action: string) => void;
}

export function MainDashboard({ playlists, selectedPlaylists, togglePlaylist, onActionSelect }: MainDashboardProps) {
  const actions = [
    { title: "Anomaly Detection", desc: "Find songs that don't belong in these playlists." },
    { title: "Mood Detection", desc: "Analyze the acoustic sentiment of your tracks." },
    { title: "Playlist Comparisons", desc: "See the overlap and differences between selections." },
    { title: "Mood Finder", desc: "Generate a new playlist based on a specific vibe." },
    { title: "Recommendations", desc: "Get AI suggestions to improve your mixes." }
  ];

  return (
    <div className="flex h-screen bg-gray-950 text-brand-lavender selection:bg-brand-cyan/20">
      {/* Left Sidebar */}
      <div className="w-80 border-r border-white/5 bg-gray-950 flex flex-col z-10">
        <div className="p-6 font-black text-xl border-b border-white/5 tracking-tighter text-white">APP_NAME</div>
        <div className="p-4 font-semibold text-xs text-brand-teal uppercase tracking-widest">Your Library</div>
        
        <ScrollArea className="flex-1 px-4">
          <div className="flex flex-col gap-2 pb-4">
            {playlists.map((p) => {
              const isSelected = selectedPlaylists.includes(p.id);
              return (
                <button 
                  key={p.id}
                  onClick={() => togglePlaylist(p.id)}
                  className={`relative flex items-center gap-4 p-3 rounded-xl transition-all duration-200 text-left w-full border outline-none focus-visible:ring-1 focus-visible:ring-brand-teal ${
                    isSelected 
                      ? 'bg-brand-indigo/20 border-brand-indigo/40' 
                      : 'bg-transparent border-transparent hover:bg-white/[0.02]'
                  }`}
                >
                  <div className={`flex items-center justify-center w-10 h-10 rounded-lg shrink-0 transition-colors ${
                    isSelected ? 'bg-brand-indigo/50 text-brand-lavender' : 'bg-gray-900 text-brand-teal/50'
                  }`}>
                    <Disc3 size={20} strokeWidth={1.5} />
                  </div>
                  
                  <div className="flex-1 overflow-hidden">
                    <h4 className={`text-sm font-medium truncate transition-colors ${
                      isSelected ? 'text-white' : 'text-brand-lavender/80'
                    }`}>
                      {p.name}
                    </h4>
                  </div>

                  <div className="shrink-0 pr-2">
                    <div className={`w-4 h-4 rounded-full border flex items-center justify-center transition-all ${
                      isSelected ? 'border-brand-cyan bg-brand-cyan text-gray-950 scale-100' : 'border-transparent bg-transparent scale-90'
                    }`}>
                      {isSelected && <Check size={10} strokeWidth={3} />}
                    </div>
                  </div>
                </button>
              );
            })}
          </div>
        </ScrollArea>
        
        <div className="p-4 border-t border-white/5 bg-gray-900/20 text-xs font-medium text-brand-teal/60">
          @spotify_user
        </div>
      </div>

      {/* Main Actions Area */}
      <div className="flex-1 p-10 overflow-y-auto bg-gray-950 relative">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_top_right,_var(--tw-gradient-stops))] from-brand-navy/10 to-transparent pointer-events-none"></div>
        <h1 className="text-3xl font-bold mb-8 tracking-tight text-white relative z-10">Select Action</h1>
        
        <div className="grid gap-4 max-w-4xl relative z-10">
          {actions.map((action) => (
            <Card 
              key={action.title}
              className="p-6 cursor-pointer bg-gray-900/40 border-white/5 hover:border-brand-teal/30 hover:bg-gray-900/80 transition-all duration-200 group"
              onClick={() => onActionSelect(action.title)}
            >
              <h3 className="font-medium text-lg text-brand-lavender2 group-hover:text-brand-cyan transition-colors">{action.title}</h3>
              <p className="text-brand-teal/70 text-sm mt-1">{action.desc}</p>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}