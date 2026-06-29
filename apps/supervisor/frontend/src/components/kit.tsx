/** Shared presentational primitives for the Supervisor app — keeps a consistent
 *  AkzoNobel dark-theme look (page width, headers, section spacing). */
import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-5xl px-6 py-8", className)}>{children}</div>;
}

export function PageHeader({
  eyebrow,
  title,
  subtitle,
  actions,
}: {
  eyebrow?: string;
  title: string;
  subtitle?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-8 flex items-start justify-between gap-4 border-b border-border pb-6">
      <div>
        {eyebrow && (
          <div className="mb-1 text-xs font-semibold uppercase tracking-wide text-primary">
            {eyebrow}
          </div>
        )}
        <h1 className="text-2xl font-bold tracking-tight text-foreground">{title}</h1>
        {subtitle && <p className="mt-2 max-w-3xl text-sm leading-relaxed text-muted-foreground">{subtitle}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function SectionTitle({ children }: { children: ReactNode }) {
  return <h2 className="text-base font-semibold text-foreground">{children}</h2>;
}

const DOMAIN_STYLES: Record<string, string> = {
  FINANCE: "border-transparent bg-[oklch(0.431_0.126_251.2)] text-white",
  SCM: "border-transparent bg-[oklch(0.603_0.131_236.8)] text-white",
  COMMERCIAL: "border-transparent bg-[oklch(0.694_0.164_318.2)] text-white",
};

export function DomainBadge({ domain }: { domain: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-2 py-0.5 text-[10px] font-bold uppercase tracking-wider",
        DOMAIN_STYLES[domain] ?? "bg-muted text-muted-foreground"
      )}
    >
      {domain}
    </span>
  );
}

export function ErrorText({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive">
      {children}
    </div>
  );
}
