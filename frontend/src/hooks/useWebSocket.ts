import { useCallback, useEffect, useRef, useState } from 'react';
import { api } from '../api/client';
import { WSEvent } from '../types';

/**
 * useQueryWebSocket — live event stream for a research run.
 *
 * Connects to /ws/<queryId> and surfaces every message as a typed WSEvent
 * (modulo ping frames, which we swallow). On unexpected disconnect the
 * hook auto-reconnects with exponential backoff so the live event feed
 * survives wifi blips and ngrok hiccups without leaving the user
 * staring at a stale "Live" dot.
 *
 * Reconnect contract
 * ------------------
 * • Up to MAX_RETRIES attempts; on the 7th failure we give up + stay
 *   disconnected.
 * • Delay schedule: `min(BASE_DELAY_MS * 2 ** retryCount, MAX_DELAY_MS)`
 *   — i.e. 800ms, 1.6s, 3.2s, 6.4s, 12.8s, 15s, 15s.
 * • A clean close (code 1000) is treated as intentional — no retry.
 * • Changing `queryId` cancels any pending reconnect for the previous
 *   query (so navigating away mid-backoff doesn't leak a future
 *   socket).
 * • Successful onopen resets `retryCount` to 0.
 *
 * Cleanup
 * -------
 * • Before closing a socket we null every handler so a late onclose
 *   from the dying socket never re-triggers our reconnect path or
 *   pokes React state after the effect has torn down.
 * • The pending reconnect timer is cleared on unmount.
 */

const MAX_RETRIES   = 6;
const BASE_DELAY_MS = 800;
const MAX_DELAY_MS  = 15_000;
const CLEAN_CLOSE_CODE = 1000;

export function useQueryWebSocket(queryId: string | null) {
  const wsRef           = useRef<WebSocket | null>(null);
  const retryTimerRef   = useRef<number | null>(null);
  const retryCountRef   = useRef(0);
  /**
   * Snapshot of the query the current effect run is responsible for.
   * Each effect run writes its own queryId here; reconnect callbacks
   * compare the captured-at-schedule value against this ref so a stale
   * retry from a previous queryId can't spawn a socket for the new one.
   */
  const activeQueryRef  = useRef<string | null>(null);

  const [events,    setEvents]    = useState<WSEvent[]>([]);
  const [connected, setConnected] = useState(false);

  const clear = useCallback(() => setEvents([]), []);

  /** Tear down the current socket without triggering its onclose handler
      (we null every callback first). Also cancels any pending reconnect
      timer so it can't fire after teardown. */
  const teardown = useCallback(() => {
    if (retryTimerRef.current !== null) {
      window.clearTimeout(retryTimerRef.current);
      retryTimerRef.current = null;
    }
    if (wsRef.current) {
      const ws = wsRef.current;
      ws.onopen = null;
      ws.onclose = null;
      ws.onerror = null;
      ws.onmessage = null;
      // Use a clean close code so any peer cleanup runs normally.
      try {
        ws.close(CLEAN_CLOSE_CODE, 'client unmounted');
      } catch {
        // ws may already be closed/closing; that's fine.
      }
      wsRef.current = null;
    }
    setConnected(false);
  }, []);

  useEffect(() => {
    // No active query → make sure nothing's connected and event log is empty.
    if (!queryId) {
      activeQueryRef.current = null;
      teardown();
      clear();
      return;
    }

    activeQueryRef.current = queryId;
    retryCountRef.current = 0;

    const connect = () => {
      // Defensive: if the active query changed while we were waiting in
      // setTimeout, drop this attempt on the floor.
      if (activeQueryRef.current !== queryId) return;

      // Replace any prior socket before opening a new one.
      if (wsRef.current) {
        const prev = wsRef.current;
        prev.onopen = null;
        prev.onclose = null;
        prev.onerror = null;
        prev.onmessage = null;
        try { prev.close(CLEAN_CLOSE_CODE); } catch { /* ignore */ }
      }

      const ws = api.createWebSocket(queryId);
      wsRef.current = ws;

      ws.onopen = () => {
        // Successful connection — reset the backoff counter.
        retryCountRef.current = 0;
        setConnected(true);
      };

      ws.onerror = () => {
        // We don't react to onerror directly; onclose will fire with a
        // code that lets us decide whether to retry.
        setConnected(false);
      };

      ws.onclose = (event) => {
        setConnected(false);

        // Intentional close from either side — no retry.
        if (event.code === CLEAN_CLOSE_CODE) return;

        // Effect's queryId is no longer active — drop the reconnect.
        if (activeQueryRef.current !== queryId) return;

        // Out of retries — surrender silently.
        if (retryCountRef.current >= MAX_RETRIES) return;

        const delay = Math.min(
          BASE_DELAY_MS * 2 ** retryCountRef.current,
          MAX_DELAY_MS,
        );
        retryCountRef.current += 1;
        retryTimerRef.current = window.setTimeout(connect, delay);
      };

      ws.onmessage = (e) => {
        try {
          const data = JSON.parse(e.data as string) as WSEvent;
          // Keepalive ping — ignore so it doesn't pollute the event log.
          if (data.event === 'ping') return;
          setEvents((prev) => [...prev, data]);
        } catch {
          // Malformed frame — skip without crashing the stream.
        }
      };
    };

    connect();

    return () => {
      // Effect cleanup — invalidate the active query first so any
      // in-flight retries bail out before they create a new socket.
      activeQueryRef.current = null;
      teardown();
    };
  }, [queryId, teardown, clear]);

  return { events, connected, clear };
}
