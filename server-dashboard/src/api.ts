import { useState, useEffect, useRef, useCallback } from 'react';

// ---------------------------------------------------------------------------
// Server URL
// ---------------------------------------------------------------------------

const STORAGE_KEY = 'qvc-server-url';
// VITE_SERVER_URL is injected by start.sh so the dashboard knows which port
// the Python server actually bound to. Falls back to the usual default.
const DEFAULT_URL = import.meta.env.VITE_SERVER_URL || 'http://localhost:5050';

export function getServerUrl(): string {
  return localStorage.getItem(STORAGE_KEY) || DEFAULT_URL;
}

export function setServerUrl(url: string): void {
  localStorage.setItem(STORAGE_KEY, url);
}

// ---------------------------------------------------------------------------
// Fetch helpers
// ---------------------------------------------------------------------------

async function apiFetch<T>(path: string): Promise<T> {
  const res = await fetch(`${getServerUrl()}${path}`);
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

async function apiPost<T>(path: string): Promise<T> {
  const res = await fetch(`${getServerUrl()}${path}`, { method: 'POST' });
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`);
  return res.json();
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export interface StatusData {
  uptime_seconds: number;
  api_state: string;
  user_count: number;
  call_count: number;
  config: {
    rest_port: number;
    websocket_port: number;
    local_ip: string;
  };
}

export interface UserInfo {
  api_endpoint: string;
  state: string;
  peer: string | null;
}

export interface EventEntry {
  timestamp: string;
  event: string;
  [key: string]: unknown;
}

export interface LogsData {
  lines: string[];
  file: string;
}

export async function fetchStatus(): Promise<StatusData> {
  return apiFetch('/admin/status');
}

export async function fetchUsers(): Promise<Record<string, UserInfo>> {
  const data = await apiFetch<{ users: Record<string, UserInfo> }>('/admin/users');
  return data.users;
}

export async function fetchEvents(limit = 50): Promise<EventEntry[]> {
  const data = await apiFetch<{ events: EventEntry[] }>(`/admin/events?limit=${limit}`);
  return data.events;
}

export async function fetchLogs(lines = 200): Promise<LogsData> {
  return apiFetch(`/admin/logs?lines=${lines}`);
}

export async function disconnectUser(userId: string): Promise<void> {
  await apiPost(`/admin/disconnect/${userId}`);
}

export async function removeUser(userId: string): Promise<void> {
  await apiPost(`/admin/remove/${userId}`);
}

// ---------------------------------------------------------------------------
// usePolling hook
// ---------------------------------------------------------------------------

export interface PollingResult<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  refresh: () => void;
}

export function usePolling<T>(
  fetchFn: () => Promise<T>,
  intervalMs: number,
): PollingResult<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const tickRef = useRef(0);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const doFetch = useCallback(async () => {
    try {
      const result = await fetchFn();
      setData(result);
      setError(null);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [fetchFn]);

  const startPolling = useCallback(() => {
    if (intervalRef.current !== null) return;
    intervalRef.current = setInterval(doFetch, intervalMs);
  }, [doFetch, intervalMs]);

  const stopPolling = useCallback(() => {
    if (intervalRef.current === null) return;
    clearInterval(intervalRef.current);
    intervalRef.current = null;
  }, []);

  useEffect(() => {
    doFetch();
    startPolling();

    const handleVisibility = () => {
      if (document.hidden) {
        stopPolling();
      } else {
        doFetch();
        startPolling();
      }
    };

    document.addEventListener('visibilitychange', handleVisibility);
    return () => {
      stopPolling();
      document.removeEventListener('visibilitychange', handleVisibility);
    };
  }, [doFetch, startPolling, stopPolling]);

  const refresh = useCallback(() => {
    tickRef.current += 1;
    doFetch();
  }, [doFetch]);

  return { data, error, loading, refresh };
}
