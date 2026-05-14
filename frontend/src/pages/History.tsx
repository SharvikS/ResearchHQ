import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Trash2, ArrowRight, Clock, TrendingUp, X, Filter } from 'lucide-react';
import { clsx } from 'clsx';
import { Layout, PageHeader } from '../components/Layout';
import { Card, Badge, Button, EmptyState } from '../components/ui';
import { useStore } from '../store';
import { HistoryEntry } from '../types';

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d}d ago`;
  return new Date(iso).toLocaleDateString();
}

function statusVariant(s: string): 'success' | 'error' | 'info' | 'warning' | 'default' {
  if (s === 'complete') return 'success';
  if (s === 'failed') return 'error';
  if (s === 'running') return 'info';
  return 'default';
}

function confidenceColor(v?: number) {
  if (!v) return 'text-slate-500';
  if (v >= 0.75) return 'text-emerald-400';
  if (v >= 0.5) return 'text-amber-400';
  return 'text-red-400';
}

export function History() {
  const navigate = useNavigate();
  const { history, removeFromHistory, clearHistory, setActiveQueryId } = useStore();
  const [q, setQ] = useState('');
  const [filterStatus, setFilterStatus] = useState<string>('all');

  const filtered = history.filter((h) => {
    const matchQuery = !q || h.query.toLowerCase().includes(q.toLowerCase()) || h.query_id.includes(q);
    const matchStatus = filterStatus === 'all' || h.status === filterStatus;
    return matchQuery && matchStatus;
  });

  function open(entry: HistoryEntry) {
    setActiveQueryId(entry.query_id);
    navigate('/workspace');
  }

  const stats = {
    total: history.length,
    complete: history.filter((h) => h.status === 'complete').length,
    avgConf: (() => {
      const vals = history.filter((h) => h.confidence).map((h) => h.confidence!);
      return vals.length ? vals.reduce((a, b) => a + b, 0) / vals.length : null;
    })(),
  };

  return (
    <Layout>
      <PageHeader
        title="Query History"
        subtitle={`${history.length} total sessions`}
        actions={
          history.length > 0 && (
            <Button variant="danger" size="sm" icon={<Trash2 className="w-3.5 h-3.5" />} onClick={() => { if (confirm('Clear all history?')) clearHistory(); }}>
              Clear all
            </Button>
          )
        }
      />

      <div className="p-6 max-w-4xl mx-auto space-y-5 animate-fade-in">

        {/* Stats */}
        {history.length > 0 && (
          <div className="grid grid-cols-3 gap-3">
            <Card className="p-4 flex items-center gap-3">
              <Clock className="w-4 h-4 text-brand-400 flex-shrink-0" />
              <div>
                <p className="text-xs text-slate-500">Total</p>
                <p className="text-xl font-semibold tabular-nums">{stats.total}</p>
              </div>
            </Card>
            <Card className="p-4 flex items-center gap-3">
              <TrendingUp className="w-4 h-4 text-emerald-400 flex-shrink-0" />
              <div>
                <p className="text-xs text-slate-500">Completed</p>
                <p className="text-xl font-semibold tabular-nums">{stats.complete}</p>
              </div>
            </Card>
            <Card className="p-4 flex items-center gap-3">
              <TrendingUp className="w-4 h-4 text-amber-400 flex-shrink-0" />
              <div>
                <p className="text-xs text-slate-500">Avg confidence</p>
                <p className="text-xl font-semibold tabular-nums">
                  {stats.avgConf != null ? `${(stats.avgConf * 100).toFixed(0)}%` : '—'}
                </p>
              </div>
            </Card>
          </div>
        )}

        {/* Filters */}
        {history.length > 0 && (
          <div className="flex items-center gap-3 flex-wrap">
            <div className="relative flex-1 max-w-xs">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search queries…"
                className="w-full bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.14] focus:border-brand-500/60 focus:ring-1 focus:ring-brand-500/30 rounded-lg pl-9 pr-3 py-2 text-sm text-slate-200 placeholder-slate-600 outline-none transition-colors"
              />
              {q && <button onClick={() => setQ('')} className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300"><X className="w-3.5 h-3.5" /></button>}
            </div>
            <div className="flex items-center gap-1.5">
              <Filter className="w-3.5 h-3.5 text-slate-500" />
              {(['all', 'complete', 'failed', 'running'] as const).map((s) => (
                <button
                  key={s}
                  onClick={() => setFilterStatus(s)}
                  className={clsx('px-2.5 py-1 rounded-full text-xs font-medium border transition-all capitalize',
                    filterStatus === s
                      ? 'bg-brand-500/20 text-brand-300 border-brand-500/40'
                      : 'text-slate-500 border-white/[0.07] hover:text-slate-300 hover:border-white/[0.14]')}
                >
                  {s}
                </button>
              ))}
            </div>
            {filtered.length !== history.length && (
              <span className="text-xs text-slate-500">{filtered.length} match{filtered.length !== 1 ? 'es' : ''}</span>
            )}
          </div>
        )}

        {/* List */}
        {history.length === 0 ? (
          <EmptyState
            icon={<Clock className="w-8 h-8" />}
            title="No research history yet"
            description="Your completed research sessions will appear here."
            action={<Button variant="primary" size="sm" onClick={() => navigate('/')}>Start a query</Button>}
          />
        ) : filtered.length === 0 ? (
          <EmptyState icon={<Search className="w-7 h-7" />} title="No results" description={`No sessions match "${q}"`} />
        ) : (
          <div className="space-y-2">
            {filtered.map((entry) => (
              <Card key={entry.query_id} hover className="px-4 py-3.5 group" onClick={() => open(entry)}>
                <div className="flex items-start gap-3">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-200 line-clamp-2 group-hover:text-brand-300 transition-colors leading-snug">{entry.query}</p>
                    <div className="flex items-center gap-2 mt-2 flex-wrap">
                      <Badge variant={statusVariant(entry.status)} dot>{entry.status}</Badge>
                      {entry.confidence != null && (
                        <span className={clsx('text-xs font-medium tabular-nums', confidenceColor(entry.confidence))}>
                          {(entry.confidence * 100).toFixed(0)}% confidence
                        </span>
                      )}
                      {entry.pipeline_mode && (
                        <span className="text-xs text-slate-600 capitalize">{entry.pipeline_mode}</span>
                      )}
                      <span className="text-xs text-slate-600 ml-auto">{timeAgo(entry.created_at)}</span>
                    </div>
                    <p className="text-[10px] text-slate-700 font-mono mt-1">{entry.query_id}</p>
                  </div>
                  <div className="flex items-center gap-1.5 flex-shrink-0 ml-2">
                    <button
                      onClick={(e) => { e.stopPropagation(); removeFromHistory(entry.query_id); }}
                      className="p-1.5 rounded text-slate-600 hover:text-red-400 hover:bg-red-500/10 transition-colors opacity-0 group-hover:opacity-100"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                    <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-brand-400 transition-colors" />
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </Layout>
  );
}
