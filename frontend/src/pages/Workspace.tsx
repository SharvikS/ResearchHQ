import { useState, useEffect, useRef, useCallback } from 'react';
import { Send, ExternalLink, ChevronDown, ChevronUp, Copy, Check, Zap, Clock, DollarSign, Brain, Search, Code2, Layers, Cpu } from 'lucide-react';
import { clsx } from 'clsx';
import { Layout, PageHeader } from '../components/Layout';
import { Card, Badge, Button, Progress, Spinner, Divider, EmptyState } from '../components/ui';
import { api } from '../api/client';
import { useStore } from '../store';
import { useQueryWebSocket } from '../hooks/useWebSocket';
import { QueryStatus, FinalResponse, PipelineStatus, WSEvent } from '../types';

const SLOT_ICONS: Record<string, typeof Brain> = {
  fast_scan: Zap,
  deep_reasoning: Brain,
  technical: Code2,
  web_synthesis: Search,
  extended_think: Cpu,
  ensemble: Layers,
  default: Brain,
};

function slotIcon(name: string) {
  return SLOT_ICONS[name] || SLOT_ICONS.default;
}

function statusColor(status: string) {
  if (status === 'complete') return 'text-emerald-400';
  if (status === 'running') return 'text-brand-400';
  if (status === 'failed' || status === 'timeout') return 'text-red-400';
  return 'text-slate-500';
}

function confidenceColor(score: number) {
  if (score >= 0.75) return 'text-emerald-400';
  if (score >= 0.5) return 'text-amber-400';
  return 'text-red-400';
}

function ConfidenceBar({ score, label }: { score: number; label: string }) {
  return (
    <div className="space-y-1">
      <div className="flex justify-between text-xs">
        <span className="text-slate-400 capitalize">{label.replace(/_/g, ' ')}</span>
        <span className={confidenceColor(score)}>{(score * 100).toFixed(0)}%</span>
      </div>
      <Progress value={score * 100} className="h-1.5" color={score >= 0.75 ? 'bg-emerald-500' : score >= 0.5 ? 'bg-amber-500' : 'bg-red-500'} />
    </div>
  );
}

function PipelineCard({ stage }: { stage: PipelineStatus }) {
  const Icon = slotIcon(stage.slot_name);
  return (
    <div className={clsx('flex items-center gap-3 p-3 rounded-lg border transition-all', {
      'border-brand-500/30 bg-brand-500/5': stage.status === 'running',
      'border-emerald-500/25 bg-emerald-500/5': stage.status === 'complete',
      'border-red-500/25 bg-red-500/5': stage.status === 'failed' || stage.status === 'timeout',
      'border-white/[0.05] bg-white/[0.02]': stage.status === 'queued',
    })}>
      <div className={clsx('w-7 h-7 rounded-md flex items-center justify-center flex-shrink-0', {
        'bg-brand-500/20': stage.status === 'running',
        'bg-emerald-500/15': stage.status === 'complete',
        'bg-red-500/15': stage.status === 'failed' || stage.status === 'timeout',
        'bg-white/[0.05]': stage.status === 'queued',
      })}>
        {stage.status === 'running'
          ? <Spinner size={14} className={statusColor(stage.status)} />
          : <Icon className={clsx('w-3.5 h-3.5', statusColor(stage.status))} />}
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-xs font-medium text-slate-200 truncate">{stage.display_name}</p>
        <p className="text-xs text-slate-500 truncate">{stage.provider}</p>
      </div>
      <div className="text-right flex-shrink-0">
        {stage.latency_ms && <p className="text-xs text-slate-500">{(stage.latency_ms / 1000).toFixed(1)}s</p>}
        {stage.error && <p className="text-xs text-red-400 truncate max-w-[80px]">{stage.error}</p>}
      </div>
    </div>
  );
}

function EventLog({ events }: { events: WSEvent[] }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => { ref.current?.scrollTo({ top: ref.current.scrollHeight, behavior: 'smooth' }); }, [events]);

  return (
    <div ref={ref} className="h-48 overflow-y-auto space-y-1 font-mono text-xs">
      {events.length === 0 && <p className="text-slate-600 p-2">Waiting for events…</p>}
      {events.map((ev, i) => (
        <div key={i} className={clsx('flex gap-2 px-2 py-0.5 rounded', {
          'text-emerald-400': ev.event?.includes('finished') || ev.event?.includes('completed'),
          'text-red-400': ev.event?.includes('failed'),
          'text-brand-400': ev.event?.includes('started'),
          'text-slate-400': !ev.event?.includes('finished') && !ev.event?.includes('failed') && !ev.event?.includes('started') && !ev.event?.includes('completed'),
        })}>
          <span className="text-slate-600 flex-shrink-0">[{ev.stage || ev.event}]</span>
          <span className="truncate">{ev.detail || ev.event}</span>
        </div>
      ))}
    </div>
  );
}

export function Workspace() {
  const { settings, activeQueryId, setActiveQueryId, addToHistory } = useStore();
  const [query, setQuery] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [status, setStatus] = useState<QueryStatus | null>(null);
  const [result, setResult] = useState<FinalResponse | null>(null);
  const [showRaw, setShowRaw] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [copied, setCopied] = useState(false);
  const { events, connected, clear } = useQueryWebSocket(activeQueryId);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const stopPolling = useCallback(() => {
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
  }, []);

  const startPolling = useCallback((qid: string) => {
    stopPolling();
    pollRef.current = setInterval(async () => {
      try {
        const s = await api.getStatus(qid);
        setStatus(s);
        if (s.status === 'complete' || s.status === 'failed') {
          stopPolling();
          if (s.status === 'complete') {
            const r = await api.getResult(qid);
            if (r.final_response) {
              setResult(r.final_response);
              addToHistory({
                query_id: qid,
                query: r.final_response.executive_summary.slice(0, 120) || query,
                status: 'complete',
                confidence: r.final_response.confidence.overall_score,
                created_at: r.final_response.created_at,
                pipeline_mode: settings.defaultPipelineMode,
              });
            }
          }
        }
      } catch { /* ignore transient poll errors */ }
    }, 2000);
  }, [stopPolling, query, settings.defaultPipelineMode, addToHistory]);

  useEffect(() => {
    if (!activeQueryId) return;
    startPolling(activeQueryId);
    return stopPolling;
  }, [activeQueryId, startPolling, stopPolling]);

  useEffect(() => () => stopPolling(), [stopPolling]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!query.trim() || submitting) return;
    setSubmitting(true);
    setResult(null);
    setStatus(null);
    clear();
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
    } catch (err) {
      alert(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  }

  function copyAnswer() {
    if (!result) return;
    navigator.clipboard.writeText(result.detailed_answer).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }

  const isRunning = status && (status.status === 'queued' || status.status === 'running');
  const isDone = status?.status === 'complete';
  const hasFailed = status?.status === 'failed';

  return (
    <Layout>
      <PageHeader
        title="Research Workspace"
        subtitle={activeQueryId ? `Query: ${activeQueryId}` : 'Submit a query to begin'}
        actions={
          <div className="flex items-center gap-2">
            {connected && <><span className="w-1.5 h-1.5 rounded-full bg-brand-400 animate-pulse" /><span className="text-xs text-brand-400">Live</span></>}
            {activeQueryId && <Button variant="ghost" size="xs" onClick={() => { setActiveQueryId(null); setStatus(null); setResult(null); clear(); }}>New query</Button>}
          </div>
        }
      />

      <div className="flex h-[calc(100vh-3.5rem)] overflow-hidden">

        {/* Left panel — query + pipeline status */}
        <div className="w-72 flex-shrink-0 border-r border-white/[0.06] flex flex-col">
          {/* Query form */}
          <div className="p-4 border-b border-white/[0.06]">
            <form onSubmit={handleSubmit} className="space-y-3">
              <textarea
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => { if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSubmit(e); }}
                placeholder="Enter your research query… (Ctrl+Enter)"
                rows={4}
                className="w-full bg-white/[0.04] border border-white/[0.08] hover:border-white/[0.14] focus:border-brand-500/60 focus:ring-1 focus:ring-brand-500/30 rounded-lg px-3 py-2.5 text-sm text-slate-200 placeholder-slate-600 resize-none outline-none transition-colors"
              />
              <div className="flex gap-2">
                {(['fast', 'balanced', 'deep'] as const).map((m) => (
                  <button
                    key={m}
                    type="button"
                    onClick={() => useStore.getState().updateSettings({ defaultPipelineMode: m })}
                    className={clsx('flex-1 py-1 rounded text-xs font-medium transition-all border',
                      settings.defaultPipelineMode === m
                        ? 'bg-brand-500/20 text-brand-300 border-brand-500/30'
                        : 'text-slate-500 border-white/[0.06] hover:text-slate-300')}
                  >
                    {m}
                  </button>
                ))}
              </div>
              <Button type="submit" variant="primary" size="sm" loading={submitting} icon={<Send className="w-3.5 h-3.5" />} className="w-full">
                {submitting ? 'Submitting…' : 'Run Research'}
              </Button>
            </form>
          </div>

          {/* Pipeline status */}
          <div className="flex-1 overflow-y-auto p-4 space-y-3">
            {status && (
              <>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-slate-500 font-medium uppercase tracking-wider">Progress</span>
                    <span className="text-xs font-medium text-slate-300">{status.progress_pct}%</span>
                  </div>
                  <Progress value={status.progress_pct} className="h-1.5" animated={!!isRunning} />
                </div>
                <Divider />
                <div className="space-y-1.5">
                  {status.pipelines.map((stage) => (
                    <PipelineCard key={stage.slot_name} stage={stage} />
                  ))}
                  {status.pipelines.length === 0 && isRunning && (
                    <div className="flex items-center gap-2 text-xs text-slate-500 p-2">
                      <Spinner size={12} />
                      <span>Initializing pipeline…</span>
                    </div>
                  )}
                </div>
              </>
            )}
            {!status && !activeQueryId && (
              <EmptyState icon={<Layers className="w-6 h-6" />} title="No active query" description="Submit a query to see the pipeline execute in real time." />
            )}
          </div>

          {/* Event log toggle */}
          {events.length > 0 && (
            <div className="border-t border-white/[0.06]">
              <button onClick={() => setShowLog(!showLog)} className="w-full flex items-center justify-between px-4 py-2 text-xs text-slate-500 hover:text-slate-300 transition-colors">
                <span>Event log ({events.length})</span>
                {showLog ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronUp className="w-3.5 h-3.5" />}
              </button>
              {showLog && (
                <div className="border-t border-white/[0.06] p-3 bg-black/20">
                  <EventLog events={events} />
                </div>
              )}
            </div>
          )}
        </div>

        {/* Main content */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* Running state */}
          {isRunning && !result && (
            <div className="flex-1 flex items-center justify-center">
              <div className="text-center space-y-4 animate-fade-in">
                <div className="w-14 h-14 rounded-2xl bg-brand-500/10 flex items-center justify-center mx-auto animate-pulse-slow">
                  <Zap className="w-7 h-7 text-brand-400" />
                </div>
                <div>
                  <p className="text-base font-medium text-slate-200">Researching…</p>
                  <p className="text-sm text-slate-500 mt-1">
                    {status?.pipelines.filter((p) => p.status === 'running').map((p) => p.display_name).join(', ') || 'Pipeline starting'}
                  </p>
                </div>
                <div className="flex items-center justify-center gap-1.5">
                  {[0, 1, 2].map((i) => (
                    <span key={i} className="w-1.5 h-1.5 rounded-full bg-brand-500 animate-bounce" style={{ animationDelay: `${i * 0.15}s` }} />
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* Failed state */}
          {hasFailed && (
            <div className="flex-1 flex items-center justify-center p-6">
              <Card className="max-w-md p-6 text-center space-y-3 border-red-500/20">
                <p className="text-base font-medium text-red-300">Research failed</p>
                <p className="text-sm text-slate-500">{status?.error || 'An unexpected error occurred.'}</p>
                <Button variant="secondary" size="sm" onClick={() => { setActiveQueryId(null); setStatus(null); }}>Try again</Button>
              </Card>
            </div>
          )}

          {/* Result */}
          {result && (
            <div className="flex-1 overflow-y-auto">
              {/* Header strip */}
              <div className="sticky top-0 z-10 px-6 py-3 bg-[#070711]/90 backdrop-blur border-b border-white/[0.06] flex items-center justify-between gap-4">
                <div className="flex items-center gap-3">
                  <Badge variant={result.confidence.label === 'high' ? 'success' : result.confidence.label === 'medium' ? 'warning' : 'error'} dot>
                    {(result.confidence.overall_score * 100).toFixed(0)}% confidence
                  </Badge>
                  <span className="text-xs text-slate-500">{result.execution_metadata.ensemble_mode} ensemble</span>
                  <span className="text-xs text-slate-600 flex items-center gap-1">
                    <Clock className="w-3 h-3" />
                    {(result.execution_metadata.total_latency_ms / 1000).toFixed(1)}s
                  </span>
                  <span className="text-xs text-slate-600 flex items-center gap-1">
                    <DollarSign className="w-3 h-3" />
                    ${result.execution_metadata.estimated_cost_usd.toFixed(4)}
                  </span>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="xs" icon={copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />} onClick={copyAnswer}>
                    {copied ? 'Copied' : 'Copy'}
                  </Button>
                  <Button variant="ghost" size="xs" onClick={() => setShowRaw(!showRaw)}>
                    {showRaw ? 'Summary' : 'Full answer'}
                  </Button>
                </div>
              </div>

              <div className="flex flex-col lg:flex-row h-full">
                {/* Answer */}
                <div className="flex-1 p-6 space-y-5 overflow-y-auto min-w-0">
                  {/* Executive summary */}
                  <Card className="p-5">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Executive Summary</h3>
                    <p className="text-sm text-slate-200 leading-relaxed">{result.executive_summary}</p>
                  </Card>

                  {/* Key findings */}
                  {result.key_findings.length > 0 && (
                    <Card className="p-5">
                      <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Key Findings</h3>
                      <ul className="space-y-2">
                        {result.key_findings.map((f, i) => (
                          <li key={i} className="flex gap-2.5 text-sm text-slate-300">
                            <span className="text-brand-500 font-mono text-xs mt-0.5 flex-shrink-0">{String(i + 1).padStart(2, '0')}</span>
                            {f}
                          </li>
                        ))}
                      </ul>
                    </Card>
                  )}

                  {/* Full answer / raw */}
                  {showRaw && result.detailed_answer && (
                    <Card className="p-5">
                      <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Detailed Answer</h3>
                      <div className="prose prose-sm prose-invert max-w-none text-slate-300 text-sm leading-relaxed whitespace-pre-wrap font-mono text-xs bg-black/20 p-4 rounded-lg overflow-auto max-h-96">
                        {result.detailed_answer}
                      </div>
                    </Card>
                  )}

                  {/* Conflicts & limitations */}
                  {result.conflicting_viewpoints.length > 0 && (
                    <Card className="p-5 border-amber-500/20">
                      <h3 className="text-xs font-semibold text-amber-500 uppercase tracking-wider mb-3">Conflicting Viewpoints</h3>
                      <ul className="space-y-1.5">
                        {result.conflicting_viewpoints.map((v, i) => <li key={i} className="text-sm text-amber-300/80">{v}</li>)}
                      </ul>
                    </Card>
                  )}
                </div>

                {/* Right panel — confidence + sources */}
                <div className="w-full lg:w-64 flex-shrink-0 border-t lg:border-t-0 lg:border-l border-white/[0.06] p-4 space-y-5 overflow-y-auto">
                  {/* Confidence breakdown */}
                  <div>
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Confidence</h3>
                    <div className="space-y-2.5">
                      <ConfidenceBar score={result.confidence.breakdown.provider_agreement} label="provider agreement" />
                      <ConfidenceBar score={result.confidence.breakdown.source_quality} label="source quality" />
                      <ConfidenceBar score={result.confidence.breakdown.factual_consistency} label="factual consistency" />
                      <ConfidenceBar score={result.confidence.breakdown.hallucination_safety} label="hallucination safety" />
                    </div>
                    {result.confidence.uncertainty_notes.length > 0 && (
                      <div className="mt-3 space-y-1">
                        {result.confidence.uncertainty_notes.map((n, i) => (
                          <p key={i} className="text-xs text-amber-400/80">{n}</p>
                        ))}
                      </div>
                    )}
                  </div>

                  <Divider />

                  {/* Sources */}
                  <div>
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3">Sources ({result.sources.length})</h3>
                    <div className="space-y-2">
                      {result.sources.map((src, i) => (
                        <a key={i} href={src.url} target="_blank" rel="noopener noreferrer"
                          className="block p-2.5 rounded-lg bg-white/[0.03] border border-white/[0.06] hover:border-brand-500/30 hover:bg-brand-500/5 transition-all group">
                          <div className="flex items-start gap-1.5">
                            <ExternalLink className="w-3 h-3 text-slate-600 group-hover:text-brand-400 flex-shrink-0 mt-0.5 transition-colors" />
                            <div className="min-w-0">
                              <p className="text-xs text-slate-300 group-hover:text-brand-300 transition-colors line-clamp-2 leading-tight">{src.title || src.domain}</p>
                              <p className="text-[10px] text-slate-600 mt-0.5 truncate">{src.domain}</p>
                            </div>
                          </div>
                        </a>
                      ))}
                    </div>
                  </div>

                  <Divider />

                  {/* Run metadata */}
                  <div className="space-y-1.5">
                    <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-2">Run Info</h3>
                    {[
                      ['Pipelines', `${result.execution_metadata.pipelines_run - result.execution_metadata.pipelines_failed}/${result.execution_metadata.pipelines_run}`],
                      ['Tokens in', result.execution_metadata.total_input_tokens.toLocaleString()],
                      ['Tokens out', result.execution_metadata.total_output_tokens.toLocaleString()],
                      ['Cost', `$${result.execution_metadata.estimated_cost_usd.toFixed(4)}`],
                    ].map(([k, v]) => (
                      <div key={k} className="flex justify-between text-xs">
                        <span className="text-slate-600">{k}</span>
                        <span className="text-slate-400 font-mono">{v}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Empty state */}
          {!activeQueryId && !isRunning && !result && (
            <div className="flex-1 flex items-center justify-center p-6">
              <div className="text-center space-y-3 animate-fade-in max-w-sm">
                <div className="w-14 h-14 rounded-2xl bg-white/[0.04] border border-white/[0.08] flex items-center justify-center mx-auto">
                  <Brain className="w-7 h-7 text-slate-600" />
                </div>
                <p className="text-base font-medium text-slate-300">Ready to research</p>
                <p className="text-sm text-slate-500">Enter a query in the left panel. Multiple specialized agents will work in parallel and synthesize a verified answer.</p>
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
