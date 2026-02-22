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
    <div className="flex h-screen bg-neutral-50 text-neutral-900">
      {/* Left Sidebar - Selected Playlists */}
      <div className="w-64 border-r bg-white flex flex-col">
        <div className="p-6 font-bold text-xl border-b bg-neutral-900 text-white">AppName</div>
        <div className="p-4 font-semibold text-sm text-neutral-500 uppercase tracking-wider">Selected Playlists</div>
        
        <ScrollArea className="flex-1 px-4">
          {selectedPlaylists.length === 0 ? (
            <div className="text-sm text-neutral-400 italic p-2">No playlists selected.</div>
          ) : (
            selectedPlaylists.map((p) => (
              <div key={p.id} className="p-2 text-sm font-medium border-b last:border-0 text-neutral-700">
                {p.name}
              </div>
            ))
          )}
        </ScrollArea>
        
        <div className="p-4 border-t bg-neutral-50">
           <Button variant="outline" className="w-full">Create Playlist</Button>
        </div>
      </div>

      {/* Main Content & Chat Area */}
      <div className="flex-1 flex flex-col relative">
        {/* Header */}
        <div className="flex items-center justify-between p-6 border-b bg-white">
          <h1 className="text-2xl font-bold">[{currentAction}]</h1>
          <Button onClick={onNewAction} variant="default">New Action</Button>
        </div>

        {/* Data Visualization Area */}
        <div className="flex-1 p-8 overflow-y-auto pb-24">
          <div className="w-full h-[500px] border-2 border-dashed border-neutral-300 rounded-xl flex flex-col items-center justify-center text-neutral-400 bg-neutral-100/50">
            <p className="font-mono text-sm mb-2">{`{ Visualizations, data, reasoning }`}</p>
            <p className="text-xs">SphinxAI Jupyter Notebook output will render here.</p>
          </div>
        </div>

        {/* Chat Bar fixed to bottom */}
        <div className="absolute bottom-0 w-full p-4 bg-white border-t">
          <div className="max-w-4xl mx-auto flex gap-3">
            <Input 
              placeholder="Ask SphinxAI to edit the above data..." 
              className="flex-1 border-neutral-300 focus-visible:ring-neutral-900"
              onKeyDown={(e) => {
                if (e.key === 'Enter') {
                  console.log("Sending to Sphinx FastAPI:", e.currentTarget.value);
                  e.currentTarget.value = ""; // clear input
                }
              }}
            />
            <Button className="bg-neutral-900 text-white hover:bg-neutral-800">Send</Button>
          </div>
        </div>
      </div>
    </div>
  );
}