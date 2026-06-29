/** Shared presentational primitives for the hub pages — keeps a consistent
 *  light-theme look (page width, headers, section spacing, track/status chips). */
import type { ReactNode } from 'react';
import { Badge } from '@databricks/appkit-ui/react';
import { cn } from '../lib/utils';

export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn('mx-auto w-full max-w-6xl px-6 py-8', className)}>{children}</div>;
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-8 flex items-start justify-between gap-4">
      <div>
        {eyebrow && (
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-primary">{eyebrow}</div>
        )}
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{title}</h1>
        {subtitle && <p className="mt-1.5 max-w-2xl text-sm text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Section({
  title,
  description,
  children,
  className,
}: {
  title?: string;
  description?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn('mb-10', className)}>
      {title && <h2 className="mb-1 text-base font-semibold text-foreground">{title}</h2>}
      {description && <p className="mb-4 text-sm text-muted-foreground">{description}</p>}
      {!description && title && <div className="mb-4" />}
      {children}
    </section>
  );
}

const DOMAIN_STYLES: Record<string, string> = {
  Finance: 'bg-[oklch(0.95_0.04_236)] text-[oklch(0.42_0.1_236)]',
  'Supply chain': 'bg-[oklch(0.95_0.04_70)] text-[oklch(0.45_0.1_70)]',
  Commercial: 'bg-[oklch(0.95_0.04_304)] text-[oklch(0.45_0.12_304)]',
  'Multi-agent': 'bg-[oklch(0.95_0.04_250)] text-[oklch(0.45_0.12_250)]',
  Platform: 'bg-[oklch(0.96_0.01_250)] text-[oklch(0.45_0.02_250)]',
  Action: 'bg-[oklch(0.95_0.04_27)] text-[oklch(0.5_0.18_27)]',
};

export function TrackBadge({ domain }: { domain: string }) {
  return (
    <span
      className={cn(
        'inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium',
        DOMAIN_STYLES[domain] ?? 'bg-muted text-muted-foreground'
      )}
    >
      {domain}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const ok = /active|succeeded|ok|submitted/i.test(status);
  return (
    <Badge variant={ok ? 'default' : 'secondary'} className={ok ? 'bg-success text-success-foreground' : ''}>
      {status}
    </Badge>
  );
}

export function EmptyState({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-border px-6 py-10 text-center text-sm text-muted-foreground">
      {children}
    </div>
  );
}

export function ErrorText({ children }: { children: ReactNode }) {
  return <div className="rounded-lg bg-[oklch(0.97_0.03_27)] px-4 py-3 text-sm text-destructive">{children}</div>;
}
