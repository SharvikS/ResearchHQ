import { useEffect, useState } from 'react';
import { Bot, Zap, Brain, Code2, Search, Cpu, Layers, Edit3, Check, X, AlertTriangle } from 'lucide-react';
import { clsx } from 'clsx';
import { Layout, PageHeader } from '../components/Layout';
import { Card, Badge, Button, Select, Spinner, EmptyState, Divider, Textarea } from '../components/ui';
import { api } from '../api/client';
import { Agent } from '../types';

const SLOT_META: Record<string, { icon: React.ElementType; color: string; description: string }> = {
  fast_scan:      { icon: Zap,    color: 'text-amber-400',  description: 'Breadth-first scan — fastest available model, 6–10 key facts per run.' },
  deep_reasoning: { icon: Brain,  color: 'text-violet-400', description: 'Chain-of-thought reasoning — explores nuance, competing views, and second-order effects.' },
  technical:      { icon: Code2,  color: 'text-sky-400',    description: 'Code and technical precision — correct syntax, complexity analysis, alternative approaches.' },
  web_synthesis:  { icon: Search, color: 'text-emerald-400',description: 'Web-grounded synthesis — weights recency, cites specific sources, flags gaps.' },
  extended_think: { icon: Cpu,    color: 'text-rose-400',   description: 'Extended inference chain — exhaustive for complexity-4/5 queries, full reasoning trace.' },
};

interface AgentCardProps {
  agent: Agent;
  enabled: boolean;
  onToggle: (id: string) => void;
  onEditPrompt: (id: string) => void;
}

function AgentCard({ agent, enabled, onToggle, onEditPrompt }: AgentCardProps) {
  const meta = SLOT_META[agent.slot] || { icon: Layers, color: 'text-slate-400', description: agent.description };
  const Icon = meta.icon;

  return (
    <Card className={clsx('p-5 transition-all', !enabled && 'opacity-60')}>
      <div className="flex items-start gap-4">
        <div className={clsx('w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0', enabled ? 'bg-white/[0.08]' : 'bg-white/[0.04]')}>
          <Icon className={clsx('w-5 h-5', enabled ? meta.color : 'text-slate-600')} />
        </div>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <h3 className="text-sm font-semibold text-slate-100">{agent.name}</h3>
            <Badge variant={enabled ? 'success' : 'default'} dot>{enabled ? 'Active' : 'Disabled'}</Badge>
            <Badge variant="default" className="font-mono">{agent.slot}</Badge>
          </div>
          <p className="text-xs text-slate-500 mt-1.5 leading-relaxed">{meta.description}</p>

          <div className="mt-3">
            <p className="text-xs text-slate-600 mb-1">Preferred providers</p>
            <div className="flex gap-1.5 flex-wrap">
              {agent.preferred_providers.map((p) => (
                <span key={p} className="px-1.5 py-0.5 rounded text-[10px] font-mono bg-white/[0.05] text-slate-400 border border-white/[0.07]">{p}</span>
              ))}
            </div>
          </div>
        </div>

        <div className="flex flex-col gap-2 flex-shrink-0">
          <button
            onClick={() => onToggle(agent.id)}
            className={clsx('w-9 h-5 rounded-full relative transition-colors flex-shrink-0', enabled ? 'bg-brand-500' : 'bg-white/[0.12]')}
          >
            <span className={clsx('absolute top-0.5 w-4 h-4 rounded-full bg-white shadow transition-transform', enabled ? 'translate-x-4' : 'translate-x-0.5')} />
          </button>
          <Button variant="ghost" size="xs" icon={<Edit3 className="w-3 h-3" />} onClick={() => onEditPrompt(agent.id)}>
            Prompt
          </Button>
        </div>
      </div>
    </Card>
  );
}

interface PromptEditorProps {
  agent: Agent;
  prompt: string;
  onChange: (v: string) => void;
  onSave: () => void;
  onClose: () => void;
}

function PromptEditor({ agent, prompt, onChange, onSave, onClose }: PromptEditorProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm animate-fade-in">
      <Card className="w-full max-w-2xl p-5 space-y-4 shadow-glass">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold text-slate-100">Edit System Prompt</h2>
            <p className="text-xs text-slate-500 mt-0.5">{agent.name} — {agent.slot}</p>
          </div>
          <button onClick={onClose} className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-white/[0.06] transition-colors">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-3 rounded-lg bg-amber-500/10 border border-amber-500/20 flex gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-400 flex-shrink-0 mt-0.5" />
          <p className="text-xs text-amber-300">Custom prompts are stored locally and override the default system prompt for this session. Server-side prompts remain unchanged.</p>
        </div>

        <Textarea
          value={prompt}
          onChange={(e) => onChange(e.target.value)}
          rows={12}
          className="font-mono text-xs"
          placeholder="Enter custom system prompt…"
        />

        <div className="flex justify-end gap-2">
          <Button variant="ghost" size="sm" onClick={onClose}>Cancel</Button>
          <Button variant="primary" size="sm" icon={<Check className="w-3.5 h-3.5" />} onClick={onSave}>Apply locally</Button>
        </div>
      </Card>
    </div>
  );
}

export function Agents() {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [pipelineModes, setPipelineModes] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [customPrompts, setCustomPrompts] = useState<Record<string, string>>({});
  const [editingId, setEditingId] = useState<string | null>(null);
  const [draftPrompt, setDraftPrompt] = useState('');
  const [selectedMode, setSelectedMode] = useState('balanced');

  useEffect(() => {
    api.getAgents()
      .then((r) => {
        setAgents(r.agents);
        setPipelineModes(r.pipeline_modes);
        setEnabled(Object.fromEntries(r.agents.map((a) => [a.id, true])));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  function toggleAgent(id: string) {
    setEnabled((prev) => ({ ...prev, [id]: !prev[id] }));
  }

  function openPromptEditor(id: string) {
    const agent = agents.find((a) => a.id === id);
    if (!agent) return;
    setDraftPrompt(customPrompts[id] || '');
    setEditingId(id);
  }

  function savePrompt() {
    if (!editingId) return;
    setCustomPrompts((prev) => ({ ...prev, [editingId]: draftPrompt }));
    setEditingId(null);
  }

  const editingAgent = agents.find((a) => a.id === editingId);
  const activeSlotsForMode = pipelineModes[selectedMode] || [];

  return (
    <Layout>
      <PageHeader title="Agent Management" subtitle={`${agents.length} agents configured`} />

      <div className="p-6 max-w-4xl mx-auto space-y-6 animate-fade-in">

        {/* Pipeline mode preview */}
        {!loading && Object.keys(pipelineModes).length > 0 && (
          <Card className="p-5">
            <h2 className="text-sm font-semibold text-slate-200 mb-3">Active agents by pipeline mode</h2>
            <div className="flex gap-2 mb-4 flex-wrap">
              {Object.keys(pipelineModes).map((m) => (
                <button
                  key={m}
                  onClick={() => setSelectedMode(m)}
                  className={clsx('px-3 py-1 rounded-full text-xs font-medium border transition-all', selectedMode === m
                    ? 'bg-brand-500/20 text-brand-300 border-brand-500/40'
                    : 'text-slate-500 border-white/[0.07] hover:text-slate-300 hover:border-white/[0.15]')}
                >
                  {m}
                </button>
              ))}
            </div>
            <div className="flex gap-2 flex-wrap">
              {activeSlotsForMode.map((slot) => {
                const meta = SLOT_META[slot];
                const Icon = meta?.icon || Bot;
                return (
                  <div key={slot} className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] border border-white/[0.07]">
                    <Icon className={clsx('w-3.5 h-3.5', meta?.color || 'text-slate-400')} />
                    <span className="text-xs text-slate-300">{slot.replace(/_/g, ' ')}</span>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        <Divider />

        {/* Agent list */}
        {loading && (
          <div className="flex items-center justify-center py-16 gap-2">
            <Spinner size={18} className="text-brand-400" />
            <span className="text-sm text-slate-500">Loading agents…</span>
          </div>
        )}

        {error && (
          <div className="p-4 rounded-xl bg-red-500/10 border border-red-500/20 text-sm text-red-300">
            Failed to load agents: {error}
          </div>
        )}

        {!loading && !error && agents.length === 0 && (
          <EmptyState icon={<Bot className="w-8 h-8" />} title="No agents available" description="Start the ResearchHQ API server to see configured agents." />
        )}

        {!loading && agents.length > 0 && (
          <div className="space-y-3">
            <div className="flex items-center justify-between mb-2">
              <h2 className="text-sm font-semibold text-slate-200">All agents</h2>
              <span className="text-xs text-slate-500">{Object.values(enabled).filter(Boolean).length} of {agents.length} active</span>
            </div>
            {agents.map((agent) => (
              <AgentCard
                key={agent.id}
                agent={agent}
                enabled={enabled[agent.id] ?? true}
                onToggle={toggleAgent}
                onEditPrompt={openPromptEditor}
              />
            ))}
          </div>
        )}
      </div>

      {/* Prompt editor modal */}
      {editingId && editingAgent && (
        <PromptEditor
          agent={editingAgent}
          prompt={draftPrompt}
          onChange={setDraftPrompt}
          onSave={savePrompt}
          onClose={() => setEditingId(null)}
        />
      )}
    </Layout>
  );
}
