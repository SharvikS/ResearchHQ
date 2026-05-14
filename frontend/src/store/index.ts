import { create } from 'zustand';
import { persist, createJSONStorage } from 'zustand/middleware';
import { AppSettings, HistoryEntry } from '../types';

export const DEFAULT_SETTINGS: AppSettings = {
  apiBaseUrl: 'http://localhost:8000',
  apiKey: '',
  defaultMode: 'research',
  defaultPipelineMode: 'balanced',
  defaultEnsembleMode: 'balanced',
  enableWebSearch: true,
  enableTechnical: true,
  maxPipelines: 5,
  providerTimeout: 60,
  theme: 'dark',
  accentColor: '#6366f1',
  fontSize: 'md',
  density: 'default',
  historyRetentionDays: 30,
  debugMode: false,
  maxCostPerQuery: 1.0,
  maxTokensPerQuery: 50000,
};

interface AppStore {
  settings: AppSettings;
  updateSettings: (updates: Partial<AppSettings>) => void;
  resetSettings: () => void;

  history: HistoryEntry[];
  addToHistory: (entry: HistoryEntry) => void;
  removeFromHistory: (queryId: string) => void;
  clearHistory: () => void;

  activeQueryId: string | null;
  setActiveQueryId: (id: string | null) => void;

  sidebarCollapsed: boolean;
  setSidebarCollapsed: (v: boolean) => void;
}

export const useStore = create<AppStore>()(
  persist(
    (set) => ({
      settings: DEFAULT_SETTINGS,
      updateSettings: (updates) =>
        set((s) => ({ settings: { ...s.settings, ...updates } })),
      resetSettings: () => set({ settings: DEFAULT_SETTINGS }),

      history: [],
      addToHistory: (entry) =>
        set((s) => ({
          history: [entry, ...s.history.filter((h) => h.query_id !== entry.query_id)].slice(0, 500),
        })),
      removeFromHistory: (queryId) =>
        set((s) => ({ history: s.history.filter((h) => h.query_id !== queryId) })),
      clearHistory: () => set({ history: [] }),

      activeQueryId: null,
      setActiveQueryId: (id) => set({ activeQueryId: id }),

      sidebarCollapsed: false,
      setSidebarCollapsed: (v) => set({ sidebarCollapsed: v }),
    }),
    {
      name: 'rhq_store',
      storage: createJSONStorage(() => localStorage),
      partialize: (s) => ({
        settings: s.settings,
        history: s.history,
        sidebarCollapsed: s.sidebarCollapsed,
      }),
    },
  ),
);
