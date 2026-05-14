import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { Send, Zap, BarChart3, Clock, TrendingUp, AlertCircle, CheckCircle2, Loader2, ArrowRight } from 'lucide-react';
import { clsx } from 'clsx';
import { Layout, PageHeader } from '../components/Layout';
import { Card, Badge, Button, Input, StatCard, EmptyState } from '../components/ui';
import { api } from '../api/client';
import { useStore } from '../store';
import { HistoryEntry } from '../types';

function confidenceVariant(score?: number) {
  if (!score) return 'default';
  if (score >= 0.75) return 'success';
  if (score >= 0.5) return 'warning';
  return 'error';
}

function statusVariant(status: string) {
  if (status === 'complete') return 'success';
  if (status === 'failed') return 'error';
  if (status === 'running') return 'info';
  return 'default';
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
}

export function Dashboard() {
  const navigate = useNavigate();
  const { settings, history, setActiveQueryId } = useStore();
  const [query, setQuery] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [serverStatus, setServerStatus] = useState<'checking' | 'ok' | 'degraded' | 'offline'>('checking');

  const recent = history.slice(0, 8);
  const totalQueries = history.length;
  const completedQueries = history.filter((h) => h.status === 'complete').length;
  const avgConfidence = history.filter((h) => h.confidence).length > 0
    ? history.filter((h) => h.confidence).reduce((a, h) => a + (h.confidence || 0), 0) / history.filter((h) => h.confidence).length
    : null;

  useEffect(() => {
    api.ready()
      .then((r) => setServerStatus(r.status === 'ready' ? 'ok' : 'degraded'))
      .catch(() => setServerStatus('offline'));
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim() || submitting) return;
    setSubmitting(true);
    try {
      const res = await api.submitQuery({
        query: query.trim(),
        mode: settings.defaultMode,
        pipeline_mode: settings.defaultPipelineMode,
        format: 'markdown',
        options: {
          ensemble_mode: settings.defaultEnsembleMode,
          enable_web_search: settings.enableWebSearch,
          enable_technical: settings.enableTechnical,
          max_pipelines: settings.maxPipelines,
        },
      });
      setActiveQueryId(res.query_id);
      navigate('/workspace');
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Failed to submit query');
    } finally {
      setSubmitting(false);
    }
  }

  function openResult(entry: HistoryEntry) {
    setActiveQueryId(entry.query_id);
    navigate('/workspace');
  }

  return (
    <Layout>
      <PageHeader
        title="Dashboard"
        subtitle="Multi-agent AI research platform"
        actions={
          <div className="flex items-center gap-2 text-xs">
            {serverStatus === 'checking' && <><Loader2 className="w-3 h-3 animate-spin text-slate-500" /><span className="text-slate-500">Connecting…</span></>}
            {serverStatus === 'ok' && <><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /><span className="text-emerald-400">API Online</span></>}
            {serverStatus === 'degraded' && <><span className="w-1.5 h-1.5 rounded-full bg-amber-400" /><span className="text-amber-400">Degraded</span></>}
            {serverStatus === 'offline' && <><span className="w-1.5 h-1.5 rounded-full bg-red-400" /><span className="text-red-400">Offline</span></>}
          </div>
        }
      />

      <div className="p-6 max-w-5xl mx-auto space-y-6 animate-fade-in">

        {/* Stats row */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          <StatCard label="Total Queries" value={totalQueries} icon={<BarChart3 className="w-4 h-4" />} />
          <StatCard label="Completed" value={completedQueries} icon={<CheckCircle2 className="w-4 h-4" />} />
          <StatCard
            label="Avg Confidence"
            value={avgConfidence != null ? `${(avgConfidence * 100).toFixed(0)}%` : '—'}
            icon={<TrendingUp className="w-4 h-4" />}
          />
          <StatCard
            label="Pipeline Mode"
            value={settings.defaultPipelineMode}
            sub={settings.defaultEnsembleMode}
            icon={<Zap className="w-4 h-4" />}
          />
        </div>

        {/* Query input */}
        <Card className="p-5">
          <h2 className="text-sm font-semibold text-slate-200 mb-3">New Research Query</h2>
          <form onSubmit={handleSubmit} className="space-y-3">
            <div className="relative">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSubmit(e); }}
                placeholder="What would you like to research? (Ctrl+Enter to submit)"
                rows={3}
                className="w-full bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.14] focus:border-brand-500/60 focus:ring-1 focus:ring-brand-500/40 rounded-lg px-4 py-3 text-slate-200 placeholder-slate-600 text-sm resize-none transition-colors outline-none"
              />
            </div>
            <div className="flex items-center justify-between gap-3">
              <div className="flex items-center gap-2 flex-wrap">
                {(['fast', 'balanced', 'deep'] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => useStore.getState().updateSettings({ defaultPipelineMode: m })}
                    className={clsx(
                      'px-3 py-1 rounded-full text-xs font-medium border transition-all',
                      settings.defaultPipelineMode === m
                        ? 'bg-brand-500/20 text-brand-300 border-brand-500/40'
                        : 'text-slate-500 border-white/[0.07] hover:border-white/[0.15] hover:text-slate-300',
                    )}
                  >
                    {m}
                  </button>
                ))}
              </div>
              <Button type="submit" variant="primary" size="md" loading={submitting} icon={<Send className="w-4 h-4" />} disabled={!query.trim()}>
                Research
              </Button>
            </div>
          </form>
        </Card>

        {/* Recent sessions */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold text-slate-200">Recent Sessions</h2>
            {history.length > 0 && (
              <Button variant="ghost" size="xs" icon={<ArrowRight className="w-3.5 h-3.5" />} onClick={() => navigate('/history')}>
                View all
              </Button>
            )}
          </div>

          {recent.length === 0 ? (
            <EmptyState
              icon={<Clock className="w-8 h-8" />}
              title="No research sessions yet"
              description="Submit a query above to start your first research session."
            />
          ) : (
            <div className="space-y-2">
              {recent.map((entry) => (
                <Card
                  key={entry.query_id}
                  hover
                  className="px-4 py-3 flex items-center gap-3 group"
                  onClick={() => openResult(entry)}
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-200 truncate group-hover:text-brand-300 transition-colors">{entry.query}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <Badge variant={statusVariant(entry.status) as 'success' | 'error' | 'info' | 'default'} dot>
                        {entry.status}
                      </Badge>
                      {entry.confidence != null && (
                        <Badge variant={confidenceVariant(entry.confidence)}>
                          {(entry.confidence * 100).toFixed(0)}% conf
                        </Badge>
                      )}
                      <span className="text-xs text-slate-600">{timeAgo(entry.created_at)}</span>
                    </div>
                  </div>
                  <ArrowRight className="w-4 h-4 text-slate-600 group-hover:text-brand-400 transition-colors flex-shrink-0" />
                </Card>
              ))}
            </div>
          )}
        </div>

        {/* Offline warning */}
        {serverStatus === 'offline' && (
          <div className="flex items-start gap-3 p-4 rounded-xl bg-red-500/10 border border-red-500/20">
            <AlertCircle className="w-4 h-4 text-red-400 flex-shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium text-red-300">Cannot reach API server</p>
              <p className="text-xs text-red-400/70 mt-0.5">
                Make sure the ResearchHQ API is running at{' '}
                <code className="font-mono">{settings.apiBaseUrl}</code>. Check Settings to update the URL.
              </p>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
