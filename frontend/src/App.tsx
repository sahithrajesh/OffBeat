import { useState, useEffect, useRef } from 'react';
import { Routes, Route, Navigate, useSearchParams, useNavigate } from 'react-router-dom';
import { MainDashboard } from './components/MainDashboard';
import { ActionDashboard } from './components/ActionDashboard';
import { Button } from '@/components/ui/button';
import { API_BASE, setToken, isAuthenticated, clearToken, AuthError } from '@/lib/auth';
import { fetchPlaylists } from '@/lib/api';
import type { Playlist } from '@/lib/api';

export type { Playlist } from '@/lib/api';

// ---------------------------------------------------------------------------
// Login page – shown at /
// ---------------------------------------------------------------------------
function LoginPage() {
  useEffect(() => {
    document.documentElement.classList.add('dark');
  }, []);

  // If already authenticated, skip straight to dashboard
  if (isAuthenticated()) {
    return <Navigate to="/home" replace />;
  }

  return (
    <div className="flex h-screen w-full items-center justify-center bg-gray-950 bg-[radial-gradient(ellipse_at_top,_var(--tw-gradient-stops))] from-brand-navy/30 via-gray-950 to-gray-950 text-brand-lavender">
      <div className="bg-white/[0.02] backdrop-blur-2xl p-12 rounded-3xl border border-white/10 shadow-[0_8px_32px_rgba(0,0,0,0.5)] flex flex-col items-center max-w-md w-full text-center">
        <h1 className="text-4xl font-extrabold tracking-tight mb-3 bg-gradient-to-br from-white via-white to-brand-teal text-transparent bg-clip-text">
          OffBeat
        </h1>
        <p className="text-brand-teal/80 mb-10 font-medium">AI-Powered Playlist Analytics</p>
        <Button
          size="lg"
          className="w-full bg-brand-cyan hover:bg-[#008be5] text-white border-0 font-semibold tracking-wide shadow-[0_0_20px_rgba(0,158,250,0.2)] hover:shadow-[0_0_25px_rgba(0,158,250,0.4)] transition-all duration-500 rounded-xl"
          onClick={() => {
            // Redirect the browser to the backend's Spotify login endpoint.
            window.location.href = `${API_BASE}/auth/login`;
          }}
        >
          Authenticate via Spotify
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Home page – /home?token=<jwt>
// Captures the token from the query string, stores it, then shows dashboard.
// ---------------------------------------------------------------------------
function HomePage() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();

  const [currentView, setCurrentView] = useState<'main' | 'action'>('main');
  const [playlists, setPlaylists] = useState<Playlist[]>([]);
  const [selectedPlaylists, setSelectedPlaylists] = useState<string[]>([]);
  const [currentAction, setCurrentAction] = useState<string>('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Track whether the token has been captured and we're ready to fetch data.
  const [ready, setReady] = useState(false);
  const fetchStarted = useRef(false);

  // Effect 1 — capture the JWT from the query string, then mark ready.
  useEffect(() => {
    document.documentElement.classList.add('dark');

    const tokenParam = searchParams.get('token');
    if (tokenParam) {
      // Persist token and strip it from the URL.
      setToken(tokenParam);
      // Strip token from URL and prepare to fetch
      navigate('/home', { replace: true });
      setReady(true);
      return;
    }

    if (!isAuthenticated()) {
      navigate('/', { replace: true });
      return;
    }

    // Token is in localStorage and URL is clean → ready to fetch.
    setReady(true);
  }, [searchParams, navigate]);

  // Effect 2 — fetch playlists once ready.  Decoupled from the token
  //            capture so we never race or skip the fetch.
  useEffect(() => {
    if (!ready) return;
    // Guard against double-invocation in StrictMode.
    if (fetchStarted.current) return;
    fetchStarted.current = true;

    const controller = new AbortController();

    fetchPlaylists(controller.signal)
      .then((data) => {
        if (!controller.signal.aborted) setPlaylists(data);
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        console.error('Failed to load playlists', err);
        // If the token is truly invalid, clear it and redirect to login.
        if (err instanceof AuthError && err.status === 401) {
          clearToken();
          navigate('/', { replace: true });
          return;
        }
        setError(err instanceof Error ? err.message : 'Failed to load playlists');
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });

    return () => {
      controller.abort();
      fetchStarted.current = false;
    };
  }, [ready]);

  // --- loading / error states ---

  if (loading) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-gray-950 text-brand-lavender">
        <p className="text-lg animate-pulse">Loading your playlists…</p>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-gray-950 text-brand-lavender">
        <div className="text-center space-y-4">
          <p className="text-red-400 font-medium">Something went wrong</p>
          <p className="text-sm text-brand-teal/60">{error}</p>
          <Button
            onClick={() => {
              setError(null);
              setLoading(true);
              setReady(false);
              // Small delay then re-trigger
              setTimeout(() => setReady(true), 100);
            }}
            className="bg-brand-cyan hover:bg-[#008be5] text-white rounded-xl"
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  // --- dashboard views ---

  if (currentView === 'action') {
    return (
      <ActionDashboard
        selectedPlaylists={playlists.filter((p) => selectedPlaylists.includes(p.spotify_id))}
        currentAction={currentAction}
        onNewAction={() => setCurrentView('main')}
      />
    );
  }

  return (
    <MainDashboard
      playlists={playlists}
      selectedPlaylists={selectedPlaylists}
      togglePlaylist={(id) => {
        setSelectedPlaylists((prev) =>
          prev.includes(id) ? prev.filter((pId) => pId !== id) : [...prev, id],
        );
      }}
      onActionSelect={(action) => {
        setCurrentAction(action);
        setCurrentView('action');
      }}
    />
  );
}

// ---------------------------------------------------------------------------
// App shell – routes
// ---------------------------------------------------------------------------
export default function App() {
  return (
    <Routes>
      <Route path="/" element={<LoginPage />} />
      <Route path="/home" element={<HomePage />} />
      {/* Catch-all: redirect unknown paths to login */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}