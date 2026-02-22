/**
 * Auth utilities – JWT token management via localStorage.
 *
 * After Spotify OAuth the backend redirects to `/home?token=<jwt>`.
 * We grab the token, persist it, and use it for every API call via
 * the `Authorization: Bearer <token>` header.
 */

const TOKEN_KEY = "hacklytics_jwt";

// Backend base URL — matches the Vite dev proxy or production deploy.
export const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8888";

// ---- token helpers -------------------------------------------------------

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken(): void {
  localStorage.removeItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

// ---- fetch wrapper -------------------------------------------------------

/** Custom error class for auth failures so callers can detect 401s. */
export class AuthError extends Error {
  status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = "AuthError";
    this.status = status;
  }
}

/**
 * Thin wrapper around `fetch` that injects the JWT Bearer header.
 * Returns the parsed JSON body. Throws on non-2xx responses.
 */
export async function apiFetch<T = unknown>(
  path: string,
  init?: RequestInit,
): Promise<T> {
  const token = getToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...(init?.headers as Record<string, string>),
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${API_BASE}${path}`, { ...init, headers });

  if (res.status === 401) {
    // Don't nuke the token automatically — the caller should decide.
    // Only redirect if we're sure the session is truly gone.
    throw new AuthError("Session expired or invalid token", 401);
  }

  if (!res.ok) {
    throw new Error(`API ${res.status}: ${await res.text()}`);
  }

  return res.json() as Promise<T>;
}
