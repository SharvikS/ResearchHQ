import { NavLink, useLocation } from 'react-router-dom';
import { clsx } from 'clsx';
import {
  LayoutDashboard, FlaskConical, History, Bot, Settings,
  ChevronLeft, ChevronRight, Zap, Moon, Sun, Monitor,
} from 'lucide-react';
import { useStore } from '../store';

const NAV = [
  { to: '/',          label: 'Dashboard',  icon: LayoutDashboard },
  { to: '/workspace', label: 'Workspace',  icon: FlaskConical },
  { to: '/history',   label: 'History',    icon: History },
  { to: '/agents',    label: 'Agents',     icon: Bot },
  { to: '/settings',  label: 'Settings',   icon: Settings },
];

const THEME_ICONS = { dark: Moon, light: Sun, system: Monitor };

export function Sidebar() {
  const { settings, updateSettings, sidebarCollapsed, setSidebarCollapsed } = useStore();
  const location = useLocation();
  const collapsed = sidebarCollapsed;

  function cycleTheme() {
    const order: Array<'dark' | 'light' | 'system'> = ['dark', 'light', 'system'];
    const idx = order.indexOf(settings.theme);
    const next = order[(idx + 1) % order.length];
    updateSettings({ theme: next });
    document.documentElement.classList.toggle('dark', next === 'dark' || (next === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches));
  }

  const ThemeIcon = THEME_ICONS[settings.theme];

  return (
    <aside className={clsx(
      'fixed inset-y-0 left-0 z-30 flex flex-col border-r border-white/[0.06] bg-[#09090f]/95 backdrop-blur-xl transition-all duration-300',
      collapsed ? 'w-14' : 'w-56',
    )}>
      {/* Logo */}
      <div className={clsx('flex items-center gap-2.5 px-3 h-14 border-b border-white/[0.06] flex-shrink-0', collapsed && 'justify-center px-0')}>
        <div className="w-7 h-7 rounded-lg bg-brand-500 flex items-center justify-center flex-shrink-0 shadow-brand">
          <Zap className="w-4 h-4 text-white" />
        </div>
        {!collapsed && <span className="font-semibold text-slate-100 tracking-tight">ResearchHQ</span>}
      </div>

      {/* Navigation */}
      <nav className="flex-1 py-3 px-2 space-y-0.5 overflow-y-auto">
        {NAV.map(({ to, label, icon: Icon }) => {
          const active = to === '/' ? location.pathname === '/' : location.pathname.startsWith(to);
          return (
            <NavLink
              key={to}
              to={to}
              title={collapsed ? label : undefined}
              className={clsx(
                'flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm font-medium transition-all duration-150',
                active
                  ? 'bg-brand-500/15 text-brand-400 border border-brand-500/20'
                  : 'text-slate-400 hover:text-slate-200 hover:bg-white/[0.05]',
                collapsed && 'justify-center px-0',
              )}
            >
              <Icon className={clsx('flex-shrink-0', active ? 'w-[18px] h-[18px]' : 'w-[18px] h-[18px]')} />
              {!collapsed && <span>{label}</span>}
            </NavLink>
          );
        })}
      </nav>

      {/* Bottom controls */}
      <div className={clsx('p-2 border-t border-white/[0.06] space-y-1', collapsed && 'flex flex-col items-center')}>
        <button
          onClick={cycleTheme}
          title={`Theme: ${settings.theme}`}
          className={clsx(
            'flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-slate-400 hover:text-slate-200 hover:bg-white/[0.05] transition-colors w-full',
            collapsed && 'justify-center px-0',
          )}
        >
          <ThemeIcon className="w-[18px] h-[18px] flex-shrink-0" />
          {!collapsed && <span className="capitalize">{settings.theme} mode</span>}
        </button>

        <button
          onClick={() => setSidebarCollapsed(!collapsed)}
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className={clsx(
            'flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm text-slate-500 hover:text-slate-300 hover:bg-white/[0.05] transition-colors w-full',
            collapsed && 'justify-center px-0',
          )}
        >
          {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          {!collapsed && <span>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
