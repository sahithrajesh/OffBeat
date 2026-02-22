import { Card } from '@/components/ui/card';
import { ScrollArea } from '@/components/ui/scroll-area';
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
    <div className="flex h-screen bg-neutral-50 text-neutral-900">
      {/* Left Sidebar */}
      <div className="w-64 border-r bg-white flex flex-col">
        <div className="p-6 font-bold text-xl border-b bg-neutral-900 text-white">AppName</div>
        <div className="p-4 font-semibold text-sm text-neutral-500 uppercase tracking-wider">Your Playlists</div>
        
        <ScrollArea className="flex-1 px-4">
          {playlists.map((p) => (
            <label key={p.id} className="flex items-center gap-3 p-2 hover:bg-neutral-100 rounded-md cursor-pointer mb-1 transition-colors">
              <input 
                type="checkbox" 
                className="w-4 h-4 rounded border-neutral-300 accent-neutral-900"
                checked={selectedPlaylists.includes(p.id)}
                onChange={() => togglePlaylist(p.id)}
              />
              <span className="text-sm font-medium">{p.name}</span>
            </label>
          ))}
        </ScrollArea>
        
        <div className="p-4 border-t bg-neutral-100 text-sm font-medium text-neutral-600">
          @spotify_user
        </div>
      </div>

      {/* Main Actions Area */}
      <div className="flex-1 p-10 overflow-y-auto">
        <h1 className="text-3xl font-bold mb-8">Actions</h1>
        <div className="grid gap-4 max-w-4xl">
          {actions.map((action) => (
            <Card 
              key={action.title}
              className="p-6 cursor-pointer hover:border-neutral-900 hover:shadow-md transition-all group"
              onClick={() => onActionSelect(action.title)}
            >
              <h3 className="font-semibold text-lg group-hover:underline decoration-2 underline-offset-4">{action.title}</h3>
              <p className="text-neutral-500 text-sm mt-2">{action.desc}</p>
            </Card>
          ))}
        </div>
      </div>
    </div>
  );
}