import { clsx } from 'clsx';
import { ReactNode, ButtonHTMLAttributes, InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes, forwardRef } from 'react';

// ── Card ──────────────────────────────────────────────────────────────────────

interface CardProps { children: ReactNode; className?: string; glass?: boolean; hover?: boolean; }
export function Card({ children, className, glass = true, hover = false }: CardProps) {
  return (
    <div className={clsx(
      'rounded-xl border transition-all duration-200',
      glass
        ? 'bg-white/[0.04] dark:bg-white/[0.03] backdrop-blur-sm border-white/[0.07]'
        : 'bg-white dark:bg-surface-800 border-slate-200 dark:border-white/[0.07]',
      hover && 'hover:border-brand-500/40 hover:bg-white/[0.07] cursor-pointer',
      'shadow-glass-sm',
      className,
    )}>
      {children}
    </div>
  );
}

// ── Badge ─────────────────────────────────────────────────────────────────────

type BadgeVariant = 'default' | 'success' | 'warning' | 'error' | 'info' | 'brand';
interface BadgeProps { children: ReactNode; variant?: BadgeVariant; className?: string; dot?: boolean; }
const badgeVariants: Record<BadgeVariant, string> = {
  default: 'bg-slate-500/20 text-slate-300 border-slate-500/30',
  success: 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30',
  warning: 'bg-amber-500/20 text-amber-300 border-amber-500/30',
  error:   'bg-red-500/20 text-red-300 border-red-500/30',
  info:    'bg-sky-500/20 text-sky-300 border-sky-500/30',
  brand:   'bg-brand-500/20 text-brand-300 border-brand-500/30',
};
const dotVariants: Record<BadgeVariant, string> = {
  default: 'bg-slate-400', success: 'bg-emerald-400', warning: 'bg-amber-400',
  error: 'bg-red-400', info: 'bg-sky-400', brand: 'bg-brand-400',
};
export function Badge({ children, variant = 'default', className, dot }: BadgeProps) {
  return (
    <span className={clsx('inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border', badgeVariants[variant], className)}>
      {dot && <span className={clsx('w-1.5 h-1.5 rounded-full', dotVariants[variant])} />}
      {children}
    </span>
  );
}

// ── Button ────────────────────────────────────────────────────────────────────

type BtnVariant = 'primary' | 'secondary' | 'ghost' | 'danger' | 'outline';
type BtnSize = 'xs' | 'sm' | 'md' | 'lg';
interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> { variant?: BtnVariant; size?: BtnSize; loading?: boolean; icon?: ReactNode; }
const btnBase = 'inline-flex items-center justify-center gap-2 font-medium rounded-lg transition-all duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/50 disabled:opacity-50 disabled:cursor-not-allowed select-none';
const btnVariants: Record<BtnVariant, string> = {
  primary:   'bg-brand-500 hover:bg-brand-600 text-white shadow-brand hover:shadow-glow active:scale-[0.98]',
  secondary: 'bg-white/[0.08] hover:bg-white/[0.14] text-slate-200 border border-white/10 hover:border-white/20 active:scale-[0.98]',
  ghost:     'text-slate-400 hover:text-slate-200 hover:bg-white/[0.06] active:scale-[0.98]',
  danger:    'bg-red-500/20 hover:bg-red-500/30 text-red-300 border border-red-500/30 hover:border-red-500/50 active:scale-[0.98]',
  outline:   'border border-brand-500/40 text-brand-400 hover:bg-brand-500/10 hover:border-brand-500/70 active:scale-[0.98]',
};
const btnSizes: Record<BtnSize, string> = {
  xs: 'text-xs px-2.5 py-1.5',
  sm: 'text-sm px-3 py-1.5',
  md: 'text-sm px-4 py-2',
  lg: 'text-base px-5 py-2.5',
};
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = 'secondary', size = 'md', loading, icon, children, className, disabled, ...props }, ref) => (
    <button ref={ref} className={clsx(btnBase, btnVariants[variant], btnSizes[size], className)} disabled={disabled || loading} {...props}>
      {loading ? <span className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" /> : icon}
      {children}
    </button>
  )
);
Button.displayName = 'Button';

// ── Input ─────────────────────────────────────────────────────────────────────

interface InputProps extends InputHTMLAttributes<HTMLInputElement> { label?: string; error?: string; hint?: string; prefix?: ReactNode; }
export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ label, error, hint, prefix, className, ...props }, ref) => (
    <div className="space-y-1.5">
      {label && <label className="block text-sm font-medium text-slate-300">{label}</label>}
      <div className="relative">
        {prefix && <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">{prefix}</span>}
        <input
          ref={ref}
          className={clsx(
            'w-full bg-white/[0.05] border rounded-lg text-slate-200 placeholder-slate-500 transition-colors',
            'focus:outline-none focus:ring-1 focus:ring-brand-500/60 focus:border-brand-500/60',
            error ? 'border-red-500/60' : 'border-white/[0.08] hover:border-white/[0.14]',
            prefix ? 'pl-10 pr-3 py-2.5' : 'px-3 py-2.5',
            'text-sm',
            className,
          )}
          {...props}
        />
      </div>
      {error && <p className="text-xs text-red-400">{error}</p>}
      {hint && !error && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  )
);
Input.displayName = 'Input';

// ── Textarea ──────────────────────────────────────────────────────────────────

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> { label?: string; error?: string; hint?: string; }
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  ({ label, error, hint, className, ...props }, ref) => (
    <div className="space-y-1.5">
      {label && <label className="block text-sm font-medium text-slate-300">{label}</label>}
      <textarea
        ref={ref}
        className={clsx(
          'w-full bg-white/[0.05] border rounded-lg text-slate-200 placeholder-slate-500 transition-colors resize-none',
          'focus:outline-none focus:ring-1 focus:ring-brand-500/60 focus:border-brand-500/60',
          error ? 'border-red-500/60' : 'border-white/[0.08] hover:border-white/[0.14]',
          'px-3 py-2.5 text-sm',
          className,
        )}
        {...props}
      />
      {error && <p className="text-xs text-red-400">{error}</p>}
      {hint && !error && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  )
);
Textarea.displayName = 'Textarea';

// ── Select ────────────────────────────────────────────────────────────────────

interface SelectProps extends SelectHTMLAttributes<HTMLSelectElement> { label?: string; hint?: string; }
export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  ({ label, hint, className, children, ...props }, ref) => (
    <div className="space-y-1.5">
      {label && <label className="block text-sm font-medium text-slate-300">{label}</label>}
      <select
        ref={ref}
        className={clsx(
          'w-full bg-surface-800 border border-white/[0.08] hover:border-white/[0.14] rounded-lg',
          'text-slate-200 text-sm px-3 py-2.5 transition-colors cursor-pointer',
          'focus:outline-none focus:ring-1 focus:ring-brand-500/60 focus:border-brand-500/60',
          className,
        )}
        {...props}
      >
        {children}
      </select>
      {hint && <p className="text-xs text-slate-500">{hint}</p>}
    </div>
  )
);
Select.displayName = 'Select';

// ── Toggle ────────────────────────────────────────────────────────────────────

interface ToggleProps { checked: boolean; onChange: (v: boolean) => void; label?: string; description?: string; size?: 'sm' | 'md'; }
export function Toggle({ checked, onChange, label, description, size = 'md' }: ToggleProps) {
  const track = size === 'sm' ? 'w-8 h-4' : 'w-10 h-5';
  const thumb = size === 'sm' ? 'w-3 h-3 top-0.5' : 'w-3.5 h-3.5 top-[3px]';
  const translate = size === 'sm' ? (checked ? 'translate-x-4' : 'translate-x-0.5') : (checked ? 'translate-x-5' : 'translate-x-0.5');
  return (
    <div className="flex items-center gap-3">
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        onClick={() => onChange(!checked)}
        className={clsx('relative rounded-full transition-colors duration-200 focus:outline-none focus:ring-2 focus:ring-brand-500/50 focus:ring-offset-1 focus:ring-offset-transparent flex-shrink-0', track, checked ? 'bg-brand-500' : 'bg-white/[0.12]')}
      >
        <span className={clsx('absolute left-0 rounded-full bg-white shadow transition-transform duration-200', thumb, translate)} />
      </button>
      {(label || description) && (
        <div>
          {label && <p className="text-sm font-medium text-slate-200">{label}</p>}
          {description && <p className="text-xs text-slate-500 mt-0.5">{description}</p>}
        </div>
      )}
    </div>
  );
}

// ── Progress Bar ──────────────────────────────────────────────────────────────

interface ProgressProps { value: number; max?: number; className?: string; color?: string; animated?: boolean; }
export function Progress({ value, max = 100, className, color = 'bg-brand-500', animated }: ProgressProps) {
  const pct = Math.min(100, Math.max(0, (value / max) * 100));
  return (
    <div className={clsx('w-full bg-white/[0.06] rounded-full overflow-hidden', className)}>
      <div
        className={clsx('h-full rounded-full transition-all duration-700', color, animated && 'relative overflow-hidden')}
        style={{ width: `${pct}%` }}
      >
        {animated && pct < 100 && (
          <span className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-[shimmer_1.5s_infinite]" />
        )}
      </div>
    </div>
  );
}

// ── Spinner ───────────────────────────────────────────────────────────────────

export function Spinner({ size = 16, className }: { size?: number; className?: string }) {
  return <span className={clsx('border-2 border-current border-t-transparent rounded-full animate-spin inline-block', className)} style={{ width: size, height: size }} />;
}

// ── Divider ───────────────────────────────────────────────────────────────────

export function Divider({ label, className }: { label?: string; className?: string }) {
  if (!label) return <hr className={clsx('border-white/[0.07]', className)} />;
  return (
    <div className={clsx('flex items-center gap-3', className)}>
      <hr className="flex-1 border-white/[0.07]" />
      <span className="text-xs text-slate-600 font-medium uppercase tracking-wider">{label}</span>
      <hr className="flex-1 border-white/[0.07]" />
    </div>
  );
}

// ── Stat Card ─────────────────────────────────────────────────────────────────

interface StatCardProps { label: string; value: string | number; sub?: string; icon?: ReactNode; trend?: 'up' | 'down' | 'neutral'; className?: string; }
export function StatCard({ label, value, sub, icon, className }: StatCardProps) {
  return (
    <Card className={clsx('p-4 flex items-start gap-3', className)}>
      {icon && <div className="mt-0.5 p-2 rounded-lg bg-brand-500/10 text-brand-400 flex-shrink-0">{icon}</div>}
      <div className="min-w-0">
        <p className="text-xs text-slate-500 font-medium uppercase tracking-wider">{label}</p>
        <p className="text-xl font-semibold text-slate-100 mt-0.5 tabular-nums">{value}</p>
        {sub && <p className="text-xs text-slate-500 mt-0.5">{sub}</p>}
      </div>
    </Card>
  );
}

// ── Empty State ───────────────────────────────────────────────────────────────

interface EmptyStateProps { icon?: ReactNode; title: string; description?: string; action?: ReactNode; }
export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center gap-3 animate-fade-in">
      {icon && <div className="text-slate-600 mb-2">{icon}</div>}
      <h3 className="text-base font-medium text-slate-300">{title}</h3>
      {description && <p className="text-sm text-slate-500 max-w-sm">{description}</p>}
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}

// ── Section Header ────────────────────────────────────────────────────────────

export function SectionHeader({ title, description, action }: { title: string; description?: string; action?: ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 mb-4">
      <div>
        <h2 className="text-base font-semibold text-slate-100">{title}</h2>
        {description && <p className="text-sm text-slate-500 mt-0.5">{description}</p>}
      </div>
      {action}
    </div>
  );
}
