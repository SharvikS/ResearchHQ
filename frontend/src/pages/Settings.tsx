import { useState } from 'react';
import { Save, RotateCcw, Eye, EyeOff, Server, Sliders, Palette, Database, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { Layout, PageHeader } from '../components/Layout';
import { Card, Button, Input, Select, Toggle, Divider } from '../components/ui';
import { useStore, DEFAULT_SETTINGS } from '../store';
import { AppSettings } from '../types';
import { clsx } from 'clsx';

function SectionTitle({ icon: Icon, title, description }: { icon: React.ElementType; title: string; description?: string }) {
  return (
    <div className="flex items-start gap-3 mb-4">
      <div className="p-2 rounded-lg bg-brand-500/10 text-brand-400 flex-shrink-0 mt-0.5">
        <Icon className="w-4 h-4" />
      </div>
      <div>
        <h2 className="text-sm font-semibold text-slate-100">{title}</h2>
        {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
      </div>
    </div>
  );
}

const ACCENT_COLORS = [
  { label: 'Indigo', value: '#6366f1' },
  { label: 'Violet', value: '#8b5cf6' },
  { label: 'Rose',   value: '#f43f5e' },
  { label: 'Cyan',   value: '#06b6d4' },
  { label: 'Emerald',value: '#10b981' },
  { label: 'Amber',  value: '#f59e0b' },
];

export function Settings() {
  const { settings, updateSettings, resetSettings } = useStore();
  const [local, setLocal] = useState<AppSettings>({ ...settings });
  const [showKey, setShowKey] = useState(false);
  const [saved, setSaved] = useState(false);

  function patch(updates: Partial<AppSettings>) {
    setLocal((s) => ({ ...s, ...updates }));
  }

  function save() {
    updateSettings(local);
    // Apply theme immediately
    document.documentElement.classList.toggle(
      'dark',
      local.theme === 'dark' || (local.theme === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches),
    );
    setSaved(true);
    setTimeout(() => setSaved(false), 2500);
  }

  function reset() {
    if (!confirm('Reset all settings to defaults?')) return;
    resetSettings();
    setLocal({ ...DEFAULT_SETTINGS });
  }

  const dirty = JSON.stringify(local) !== JSON.stringify(settings);

  return (
    <Layout>
      <PageHeader
        title="Settings"
        subtitle="Configure your research platform"
        actions={
          <div className="flex items-center gap-2">
            <Button variant="ghost" size="sm" icon={<RotateCcw className="w-3.5 h-3.5" />} onClick={reset}>Reset</Button>
            <Button variant="primary" size="sm" loading={false} icon={saved ? <CheckCircle2 className="w-3.5 h-3.5" /> : <Save className="w-3.5 h-3.5" />} onClick={save} disabled={!dirty && !saved}>
              {saved ? 'Saved!' : 'Save changes'}
            </Button>
          </div>
        }
      />

      <div className="p-6 max-w-3xl mx-auto space-y-6 animate-fade-in">

        {/* Connection */}
        <Card className="p-5">
          <SectionTitle icon={Server} title="Connection" description="API server location and authentication" />
          <div className="space-y-4">
            <Input
              label="API Base URL"
              value={local.apiBaseUrl}
              onChange={(e) => patch({ apiBaseUrl: e.target.value })}
              hint="The URL where your ResearchHQ API server is running"
              placeholder="http://localhost:8000"
            />
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-slate-300">API Key</label>
              <div className="relative">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={local.apiKey}
                  onChange={(e) => patch({ apiKey: e.target.value })}
                  placeholder="rhq_… (leave empty if auth is disabled)"
                  className="w-full bg-white/[0.05] border border-white/[0.08] hover:border-white/[0.14] focus:border-brand-500/60 focus:ring-1 focus:ring-brand-500/40 rounded-lg px-3 py-2.5 pr-10 text-sm text-slate-200 placeholder-slate-600 outline-none transition-colors"
                />
                <button type="button" onClick={() => setShowKey(!showKey)} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 hover:text-slate-300 transition-colors">
                  {showKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
              <p className="text-xs text-slate-500">Set via X-API-Key header. Only required if RHQ_REQUIRE_AUTH=true on the server.</p>
            </div>
          </div>
        </Card>

        {/* Pipeline */}
        <Card className="p-5">
          <SectionTitle icon={Sliders} title="Pipeline" description="Default research execution settings" />
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <Select label="Default pipeline mode" value={local.defaultPipelineMode} onChange={(e) => patch({ defaultPipelineMode: e.target.value as AppSettings['defaultPipelineMode'] })}>
                <option value="fast">Fast — 2 agents, quick scan</option>
                <option value="balanced">Balanced — 3 agents, thorough</option>
                <option value="deep">Deep — 5 agents, exhaustive</option>
              </Select>
              <Select label="Ensemble mode" value={local.defaultEnsembleMode} onChange={(e) => patch({ defaultEnsembleMode: e.target.value })}>
                <option value="cheap">Cheap — fast + affordable</option>
                <option value="balanced">Balanced</option>
                <option value="max_confidence">Max confidence</option>
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-300">Max parallel pipelines</label>
                <input type="number" min={1} max={10} value={local.maxPipelines} onChange={(e) => patch({ maxPipelines: Number(e.target.value) })}
                  className="w-full bg-white/[0.05] border border-white/[0.08] rounded-lg px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-brand-500/60 focus:ring-1 focus:ring-brand-500/40 transition-colors" />
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-300">Provider timeout (s)</label>
                <input type="number" min={10} max={300} value={local.providerTimeout} onChange={(e) => patch({ providerTimeout: Number(e.target.value) })}
                  className="w-full bg-white/[0.05] border border-white/[0.08] rounded-lg px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-brand-500/60 focus:ring-1 focus:ring-brand-500/40 transition-colors" />
              </div>
            </div>
            <Divider />
            <div className="space-y-3">
              <Toggle checked={local.enableWebSearch} onChange={(v) => patch({ enableWebSearch: v })} label="Enable web search" description="Include live web results in research queries" />
              <Toggle checked={local.enableTechnical} onChange={(v) => patch({ enableTechnical: v })} label="Enable technical analysis" description="Activate the technical agent slot for code/algorithm queries" />
            </div>
          </div>
        </Card>

        {/* Appearance */}
        <Card className="p-5">
          <SectionTitle icon={Palette} title="Appearance" description="Theme, typography, and layout preferences (apply immediately on save)" />
          <div className="space-y-4">
            <div className="grid grid-cols-3 gap-3">
              {(['dark', 'light', 'system'] as const).map((t) => (
                <button
                  key={t}
                  type="button"
                  onClick={() => patch({ theme: t })}
                  className={clsx(
                    'py-2.5 rounded-lg text-sm font-medium border transition-all capitalize',
                    local.theme === t
                      ? 'bg-brand-500/20 text-brand-300 border-brand-500/40'
                      : 'text-slate-400 border-white/[0.07] hover:border-white/[0.15] hover:text-slate-200',
                  )}
                >
                  {t}
                </button>
              ))}
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-300 mb-2">Accent color</label>
              <div className="flex gap-2">
                {ACCENT_COLORS.map((c) => (
                  <button
                    key={c.value}
                    type="button"
                    title={c.label}
                    onClick={() => patch({ accentColor: c.value })}
                    className={clsx('w-7 h-7 rounded-full border-2 transition-all', local.accentColor === c.value ? 'border-white scale-110' : 'border-transparent scale-100 hover:scale-105')}
                    style={{ backgroundColor: c.value }}
                  />
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <Select label="Font size" value={local.fontSize} onChange={(e) => patch({ fontSize: e.target.value as AppSettings['fontSize'] })}>
                <option value="sm">Small</option>
                <option value="md">Medium</option>
                <option value="lg">Large</option>
              </Select>
              <Select label="Layout density" value={local.density} onChange={(e) => patch({ density: e.target.value as AppSettings['density'] })}>
                <option value="compact">Compact</option>
                <option value="default">Default</option>
                <option value="comfortable">Comfortable</option>
              </Select>
            </div>
          </div>
        </Card>

        {/* History & Data */}
        <Card className="p-5">
          <SectionTitle icon={Database} title="History & Data" description="Query history retention and storage" />
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="block text-sm font-medium text-slate-300">History retention (days)</label>
              <input type="number" min={1} max={365} value={local.historyRetentionDays} onChange={(e) => patch({ historyRetentionDays: Number(e.target.value) })}
                className="w-full bg-white/[0.05] border border-white/[0.08] rounded-lg px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-brand-500/60 focus:ring-1 focus:ring-brand-500/40 transition-colors max-w-xs" />
            </div>
          </div>
        </Card>

        {/* Advanced */}
        <Card className="p-5">
          <SectionTitle icon={ShieldCheck} title="Advanced" description="Cost limits and debug options" />
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-300">Max cost per query ($)</label>
                <input type="number" min={0} max={100} step={0.1} value={local.maxCostPerQuery}
                  onChange={(e) => patch({ maxCostPerQuery: Number(e.target.value) })}
                  className="w-full bg-white/[0.05] border border-white/[0.08] rounded-lg px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-brand-500/60 transition-colors" />
              </div>
              <div className="space-y-1.5">
                <label className="block text-sm font-medium text-slate-300">Max tokens per query</label>
                <input type="number" min={1000} max={500000} step={1000} value={local.maxTokensPerQuery}
                  onChange={(e) => patch({ maxTokensPerQuery: Number(e.target.value) })}
                  className="w-full bg-white/[0.05] border border-white/[0.08] rounded-lg px-3 py-2.5 text-sm text-slate-200 outline-none focus:border-brand-500/60 transition-colors" />
              </div>
            </div>
            <Toggle checked={local.debugMode} onChange={(v) => patch({ debugMode: v })} label="Debug mode" description="Show raw API responses and verbose event logs in the Workspace" />
          </div>
        </Card>

        {/* Sticky save bar when dirty */}
        {dirty && (
          <div className="fixed bottom-6 left-1/2 -translate-x-1/2 animate-slide-up z-50">
            <div className="flex items-center gap-3 px-4 py-3 rounded-xl bg-surface-800 border border-white/[0.12] shadow-glass">
              <span className="text-sm text-slate-300">You have unsaved changes</span>
              <Button variant="ghost" size="sm" onClick={() => setLocal({ ...settings })}>Discard</Button>
              <Button variant="primary" size="sm" icon={<Save className="w-3.5 h-3.5" />} onClick={save}>Save now</Button>
            </div>
          </div>
        )}
      </div>
    </Layout>
  );
}
