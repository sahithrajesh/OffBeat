import { useState, useEffect } from 'react';
import { MainDashboard } from './components/MainDashboard';
import { ActionDashboard } from './components/ActionDashboard';
import { Button } from '@/components/ui/button';

export type Playlist = { id: string; name: string };

export default function App() {
  useEffect(() => {
    document.documentElement.classList.add('dark');
  }, []);

  const [currentView, setCurrentView] = useState<'login' | 'main' | 'action'>('login');
  
  const [playlists] = useState<Playlist[]>([
    { id: '1', name: "Focus Flow" },
    { id: '2', name: "Late Night Coding" },
    { id: '3', name: "Gym Mix" },
    { id: '4', name: "Discover Weekly" }
  ]);
  const [selectedPlaylists, setSelectedPlaylists] = useState<string[]>([]);
  const [currentAction, setCurrentAction] = useState<string>("");

  if (currentView === 'login') {
    return (
      <div className="flex h-[100dvh] w-full items-center justify-center bg-gray-950 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-brand-navy/20 to-transparent text-brand-lavender px-4">
        <div className="bg-gray-900/40 backdrop-blur-md p-8 sm:p-12 rounded-2xl border border-white/5 shadow-2xl flex flex-col items-center max-w-sm sm:max-w-md w-full">
          <h1 className="text-2xl sm:text-4xl font-extrabold tracking-tight mb-2 text-white text-center">
            Hacklytics App
          </h1>
          <p className="text-brand-teal mb-6 sm:mb-8 font-medium text-sm sm:text-base text-center">AI-Powered Playlist Analytics</p>
          <Button 
            size="lg" 
            className="bg-brand-cyan hover:bg-[#007acc] text-white border-0 transition-colors"
            onClick={() => setCurrentView('main')}
          >
            Authenticate via Spotify
          </Button>
        </div>
      </div>
    );
  }

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