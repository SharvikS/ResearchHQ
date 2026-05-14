import { ReactNode } from 'react';
import { clsx } from 'clsx';
import { useStore } from '../store';
import { Sidebar } from './Sidebar';

export function Layout({ children }: { children: ReactNode }) {
  const collapsed = useStore((s) => s.sidebarCollapsed);

  return (
    <div className="min-h-screen bg-[#070711] text-slate-100 font-sans">
      {/* Background grid */}
      <div className="fixed inset-0 bg-grid-dark bg-grid opacity-100 pointer-events-none" />
      {/* Ambient glow */}
      <div className="fixed top-0 left-1/2 -translate-x-1/2 w-[600px] h-[300px] bg-brand-500/5 blur-[120px] rounded-full pointer-events-none" />

      <Sidebar />

      <main className={clsx(
        'relative min-h-screen transition-all duration-300',
        collapsed ? 'ml-14' : 'ml-56',
      )}>
        {children}
      </main>
    </div>
  );
}

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <header className="sticky top-0 z-20 flex items-center justify-between px-6 h-14 border-b border-white/[0.06] bg-[#070711]/80 backdrop-blur-xl">
      <div>
        <h1 className="text-base font-semibold text-slate-100">{title}</h1>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}
