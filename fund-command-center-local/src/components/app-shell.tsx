import { useState, type ReactNode } from "react";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { AppSidebar } from "./app-sidebar";
import { TopBar, StatusBar } from "./top-bar";
import { CommandPalette } from "./command-palette";
import { WelcomeModal } from "./welcome-modal";
import { Toaster } from "@/components/ui/sonner";

export function AppShell({ children }: { children: ReactNode }) {
  const [cmdOpen, setCmdOpen] = useState(false);
  return (
    <SidebarProvider>
      <div className="min-h-screen flex w-full bg-background">
        <AppSidebar />
        <SidebarInset className="flex min-w-0 flex-1 flex-col">
          <TopBar onOpenCommand={() => setCmdOpen(true)} />
          <StatusBar />
          <main className="flex-1 min-w-0 overflow-x-hidden">
            {children}
          </main>
          <footer className="border-t border-border/70 bg-card/30 px-4 py-2 text-[11px] text-muted-foreground">
            Prototype for research and operational design. Not investment advice. No live execution.
          </footer>
        </SidebarInset>
      </div>
      <CommandPalette open={cmdOpen} onOpenChange={setCmdOpen} />
      <WelcomeModal />
      <Toaster />
    </SidebarProvider>
  );
}

export function PageHeader({
  title, subtitle, actions, kicker,
}: { title: string; subtitle?: string; actions?: ReactNode; kicker?: string }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4 border-b border-border/70 bg-background/60 px-6 pb-4 pt-5">
      <div className="min-w-0">
        {kicker && (
          <div className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground mb-1">{kicker}</div>
        )}
        <h1 className="display text-2xl font-semibold tracking-tight text-foreground">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-muted-foreground max-w-2xl">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({
  title, subtitle, actions, children, className = "",
}: { title?: string; subtitle?: string; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`rounded-md border border-border/70 bg-card/40 ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 px-4 py-2.5">
          <div className="min-w-0">
            {title && <div className="text-sm font-semibold tracking-tight">{title}</div>}
            {subtitle && <div className="text-[11px] text-muted-foreground mt-0.5">{subtitle}</div>}
          </div>
          {actions && <div className="flex items-center gap-2">{actions}</div>}
        </header>
      )}
      <div className="p-4">{children}</div>
    </section>
  );
}

