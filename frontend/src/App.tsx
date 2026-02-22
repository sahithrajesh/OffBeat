import { useState } from 'react';
import { MainDashboard } from './components/MainDashboard';
import { ActionDashboard } from './components/ActionDashboard';
import { Button } from '@/components/ui/button';

// Mock types for our data
export type Playlist = { id: string; name: string };

export default function App() {
  const [currentView, setCurrentView] = useState<'login' | 'main' | 'action'>('login');
  
  // Mock Spotify Data
  const [playlists] = useState<Playlist[]>([
    { id: '1', name: "Focus Flow" },
    { id: '2', name: "Late Night Coding" },
    { id: '3', name: "Gym Mix" },
    { id: '4', name: "Discover Weekly" }
  ]);
  const [selectedPlaylists, setSelectedPlaylists] = useState<string[]>([]);
  const [currentAction, setCurrentAction] = useState<string>("");

  // View 1: Sign In / Auth
  if (currentView === 'login') {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-neutral-100">
        <div className="bg-white p-12 rounded-xl shadow-lg border flex flex-col items-center">
          <h1 className="text-3xl font-bold mb-2">Hacklytics App</h1>
          <p className="text-neutral-500 mb-8">AI-Powered Playlist Analytics</p>
          <Button size="lg" onClick={() => setCurrentView('main')}>
            Login with Spotify
          </Button>
        </div>
      </div>
    );
  }

  // View 2: Main Dashboard
  if (currentView === 'main') {
    return (
      <MainDashboard 
        playlists={playlists}
        selectedPlaylists={selectedPlaylists}
        togglePlaylist={(id) => {
          setSelectedPlaylists(prev => 
            prev.includes(id) ? prev.filter(pId => pId !== id) : [...prev, id]
          );
        }}
        onActionSelect={(action) => {
          setCurrentAction(action);
          setCurrentView('action');
        }}
      />
    );
  }

  // View 3: Action Dashboard
  if (currentView === 'action') {
    return (
      <ActionDashboard 
        selectedPlaylists={playlists.filter(p => selectedPlaylists.includes(p.id))}
        currentAction={currentAction}
        onNewAction={() => setCurrentView('main')}
      />
    );
  }

  return null;
}