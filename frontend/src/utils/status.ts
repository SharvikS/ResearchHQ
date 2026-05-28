/**
 * Status + confidence variant resolvers.
 *
 * Centralised so badges, dots, and progress bars across the app stay
 * colour-consistent. Every UI surface that has to render a status
 * routes through one of these — change a threshold here and the whole
 * app stays in sync.
 */

export type StatusVariant = 'success' | 'error' | 'info' | 'warning' | 'default';

/** Resolve a query/pipeline lifecycle string to a semantic variant. */
export function statusVariant(status: string): StatusVariant {
  switch (status) {
    case 'complete': return 'success';
    case 'failed':   return 'error';
    case 'running':  return 'info';
    case 'queued':   return 'warning';
    default:         return 'default';
  }
}

// Confidence thresholds — anything ≥ HIGH renders green, ≥ MEDIUM amber, else red.
// Tuned to match the verifier's label boundaries on the backend.
const CONF_HIGH   = 0.75;
const CONF_MEDIUM = 0.5;

function bandFor(score?: number): 'high' | 'medium' | 'low' | 'unknown' {
  if (score == null) return 'unknown';
  if (score >= CONF_HIGH)   return 'high';
  if (score >= CONF_MEDIUM) return 'medium';
  return 'low';
}

/** Map a confidence score (0–1) to a semantic variant for Badge styling. */
export function confidenceVariant(score?: number): StatusVariant {
  switch (bandFor(score)) {
    case 'high':   return 'success';
    case 'medium': return 'warning';
    case 'low':    return 'error';
    default:       return 'default';
  }
}

/** Tailwind text-colour class for the band a confidence score falls into. */
export function confidenceColor(score?: number): string {
  switch (bandFor(score)) {
    case 'high':   return 'text-emerald-400';
    case 'medium': return 'text-amber-400';
    case 'low':    return 'text-red-400';
    default:       return 'text-slate-500';
  }
}

/** Tailwind background-colour class for the same band (used by progress bars). */
export function confidenceBgColor(score?: number): string {
  switch (bandFor(score)) {
    case 'high':   return 'bg-emerald-500';
    case 'medium': return 'bg-amber-500';
    case 'low':    return 'bg-red-500';
    default:       return 'bg-slate-500';
  }
}
