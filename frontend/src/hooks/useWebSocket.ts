import { useEffect, useRef, useState, useCallback } from 'react';
import { api } from '../api/client';
import { WSEvent } from '../types';

export function useQueryWebSocket(queryId: string | null) {
  const wsRef = useRef<WebSocket | null>(null);
  const [events, setEvents] = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);

  const clear = useCallback(() => setEvents([]), []);

  const disconnect = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.onopen = null;
      wsRef.current.onclose = null;
      wsRef.current.onerror = null;
      wsRef.current.onmessage = null;
      wsRef.current.close();
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    if (!queryId) {
      disconnect();
      clear();
      return;
    }

    disconnect();
    const ws = api.createWebSocket(queryId);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);
    ws.onmessage = (e) => {
      try {
        const data = JSON.parse(e.data as string) as WSEvent;
        if (data.event === 'ping') return;
        setEvents((prev) => [...prev, data]);
      } catch { /* ignore malformed frames */ }
    };

    return disconnect;
  }, [queryId, disconnect, clear]);

  return { events, connected, clear };
}
