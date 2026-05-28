/**
 * Time + duration formatters used across history rows, analytics
 * tooltips, and the workspace status strip.
 */

const MINUTE = 60 * 1000;
const HOUR   = 60 * MINUTE;
const DAY    = 24 * HOUR;
const WEEK   = 7 * DAY;

/**
 * Human-friendly "time since" string from an ISO timestamp.
 *
 *   < 1m   → "just now"
 *   < 1h   → "Nm ago"
 *   < 1d   → "Nh ago"
 *   < 7d   → "Nd ago"
 *   else   → localized date ("Mar 5, 2026")
 */
export function timeAgo(iso: string): string {
  const elapsed = Date.now() - new Date(iso).getTime();

  if (elapsed < MINUTE) return 'just now';
  if (elapsed < HOUR)   return `${Math.floor(elapsed / MINUTE)}m ago`;
  if (elapsed < DAY)    return `${Math.floor(elapsed / HOUR)}h ago`;
  if (elapsed < WEEK)   return `${Math.floor(elapsed / DAY)}d ago`;

  return new Date(iso).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

/**
 * Render a duration as "1234ms" / "1.2s" / "3m 14s".
 * Used for latency badges + per-run timing panels.
 */
export function formatDuration(ms: number): string {
  if (ms < 1000)  return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;

  const minutes = Math.floor(ms / 60000);
  const seconds = Math.round((ms % 60000) / 1000);
  return `${minutes}m ${seconds}s`;
}
