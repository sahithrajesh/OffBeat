import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Playlist } from '../App';

interface ActionDashboardProps {
  selectedPlaylists: Playlist[];
  currentAction: string;
  onNewAction: () => void;
}

export function ActionDashboard({ selectedPlaylists, currentAction, onNewAction }: ActionDashboardProps) {
  return (
    <div className="flex h-screen bg-gray-950 text-brand-lavender selection:bg-brand-cyan/20">
      {/* Left Sidebar */}
      <div className="w-80 border-r border-white/5 bg-gray-950 flex flex-col z-10">
        <div className="p-6 font-black text-xl border-b border-white/5 tracking-tighter text-white">APP_NAME</div>
        <div className="p-4 font-semibold text-xs text-brand-teal uppercase tracking-widest">Active Scope</div>
        
        <ScrollArea className="flex-1 px-4">
          {selectedPlaylists.length === 0 ? (
            <div className="text-sm text-brand-teal/40 italic p-2">No playlists selected.</div>
          ) : (
            selectedPlaylists.map((p) => (
              <div key={p.id} className="p-3 text-sm font-medium border-b border-white/5 last:border-0 text-brand-lavender/80">
                {p.name}
              </div>
            ))
          )}
        </ScrollArea>
        
        <div className="p-4 border-t border-white/5">
           <Button variant="outline" className="w-full border-white/10 text-brand-lavender hover:bg-white/5 hover:text-white bg-transparent transition-colors">
             Save Selection
           </Button>
        </div>
      </div>

      {/* Main Content & Chat Area */}
      <div className="flex-1 flex flex-col relative bg-gray-950">
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_bottom_right,_var(--tw-gradient-stops))] from-brand-plum/10 to-transparent pointer-events-none"></div>
        
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b border-white/5 bg-gray-950/80 backdrop-blur-md z-10">
          <div className="flex items-center gap-4">
            <h1 className="text-xl font-semibold tracking-tight text-white">{currentAction}</h1>
            <div className="px-2 py-1 rounded bg-brand-magenta/10 text-brand-lavender text-[10px] uppercase tracking-wider font-semibold border border-brand-magenta/20">
              Processing
            </div>
          </div>
          <Button onClick={onNewAction} variant="ghost" className="text-brand-teal hover:text-white hover:bg-white/5">
            Back to Actions
          </Button>
        </div>

        {/* Data Visualization Area */}
        <div className="flex-1 p-8 overflow-y-auto pb-32 relative z-10">
          <div className="w-full h-[600px] border border-white/5 rounded-xl flex flex-col items-center justify-center text-brand-teal/60 bg-gray-900/30 relative overflow-hidden">
            {/* Very faint grid */}
            <div className="absolute inset-0 bg-[linear-gradient(to_right,#5693A508_1px,transparent_1px),linear-gradient(to_bottom,#5693A508_1px,transparent_1px)] bg-[size:24px_24px]"></div>
            
            <div className="relative z-10 flex flex-col items-center">
              <div className="w-12 h-12 border-2 border-brand-indigo/30 border-t-brand-teal rounded-full animate-spin mb-4"></div>
              <p className="font-mono text-sm">{`{ Waiting for SphinxAI... }`}</p>
            </div>
          </div>
        </div>

        {/* Chat Bar */}
        <div className="absolute bottom-0 w-full p-6 bg-gradient-to-t from-gray-950 via-gray-950 to-transparent z-20">
          <div className="max-w-4xl mx-auto flex gap-3 bg-gray-900/80 p-1.5 rounded-xl border border-white/10 backdrop-blur-md shadow-lg">
            <Input 
              placeholder="Ask SphinxAI to slice the data differently..." 
              className="flex-1 border-0 bg-transparent text-white placeholder:text-brand-teal/50 focus-visible:ring-0 text-sm px-4"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  console.log("Sending to Sphinx FastAPI:", e.currentTarget.value);
                  e.currentTarget.value = ""; 
                }
              }}
            />
            <Button className="bg-brand-cyan hover:bg-[#007acc] text-white rounded-lg px-6 transition-colors">
              Send
            </Button>
          </div>
        </div>
      </div>
    </div>
  );
}