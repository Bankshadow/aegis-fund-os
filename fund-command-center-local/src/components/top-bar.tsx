import { useEffect, useState } from "react";
import { Bell, Search, ChevronDown, Command, User2, Signal, Clock } from "lucide-react";
import { SidebarTrigger } from "@/components/ui/sidebar";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import {
  DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel,
  DropdownMenuSeparator, DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { PaperBadge, StatusDot } from "./demo-tag";
import { FUND } from "@/lib/demo-data";

interface TopBarProps {
  onOpenCommand: () => void;
}

export function TopBar({ onOpenCommand }: TopBarProps) {
  const [now, setNow] = useState<string>("");
  useEffect(() => {
    const tick = () => {
      const d = new Date();
      setNow(d.toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: "Asia/Bangkok" }));
    };
    tick();
    const t = setInterval(tick, 1000);
    return () => clearInterval(t);
  }, []);

  return (
    <header className="sticky top-0 z-30 flex h-14 items-center gap-3 border-b border-border/80 bg-background/95 px-3 backdrop-blur">
      <SidebarTrigger className="text-muted-foreground hover:text-foreground" />
      <Separator orientation="vertical" className="h-6" />

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="gap-2 px-2 text-sm">
            <div className="grid h-6 w-6 place-items-center rounded-sm bg-primary/15 text-primary text-[10px] font-bold ring-1 ring-primary/30">A</div>
            <div className="hidden sm:flex flex-col items-start leading-tight">
              <span className="text-[13px] font-semibold">{FUND.name}</span>
              <span className="text-[10px] text-muted-foreground tracking-wide">{FUND.code} · {FUND.baseCurrency} · {FUND.timezone}</span>
            </div>
            <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="start" className="w-64">
          <DropdownMenuLabel>Switch Fund</DropdownMenuLabel>
          <DropdownMenuItem>Aegis Global Opportunities Fund I <span className="ml-auto text-[10px] text-muted-foreground">active</span></DropdownMenuItem>
          <DropdownMenuItem disabled>Aegis Systematic Macro II <span className="ml-auto text-[10px] text-muted-foreground">demo</span></DropdownMenuItem>
          <DropdownMenuItem disabled>Aegis Digital Yield SP <span className="ml-auto text-[10px] text-muted-foreground">demo</span></DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>

      <div className="hidden md:flex items-center gap-2 rounded-md border border-border/70 bg-card/40 px-2 py-1 text-xs text-muted-foreground">
        <Clock className="h-3.5 w-3.5" />
        <span className="num">As of 2025-11-14</span>
        <Separator orientation="vertical" className="h-3" />
        <span className="num">{now} ICT</span>
      </div>

      <button
        onClick={onOpenCommand}
        className="ml-auto flex min-w-0 max-w-md flex-1 items-center gap-2 rounded-md border border-border/70 bg-card/40 px-2.5 py-1.5 text-left text-sm text-muted-foreground transition hover:border-border hover:bg-card/70"
      >
        <Search className="h-3.5 w-3.5 shrink-0" />
        <span className="truncate">Search accounts, tickers, events, reports…</span>
        <kbd className="ml-auto hidden sm:inline-flex items-center gap-1 rounded border border-border/60 bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground">
          <Command className="h-3 w-3" /> K
        </kbd>
      </button>

      <PaperBadge className="hidden md:inline-flex" />

      <div className="hidden lg:flex items-center gap-1.5 rounded-md border border-border/70 px-2 py-1 text-[11px] text-muted-foreground">
        <Signal className="h-3 w-3 text-positive" /> <span>Fresh · 2s</span>
      </div>

      <Button variant="ghost" size="icon" className="relative">
        <Bell className="h-4 w-4" />
        <span className="absolute right-1.5 top-1.5 h-1.5 w-1.5 rounded-full bg-warning" />
      </Button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <Button variant="ghost" size="sm" className="gap-2 px-1.5">
            <div className="grid h-7 w-7 place-items-center rounded-full bg-accent text-accent-foreground text-[11px] font-semibold">AN</div>
            <div className="hidden md:flex flex-col items-start leading-tight">
              <span className="text-[12px] font-medium">Anong K.</span>
              <span className="text-[10px] text-muted-foreground">COO / Ops</span>
            </div>
          </Button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end" className="w-52">
          <DropdownMenuLabel>Signed in · Demo</DropdownMenuLabel>
          <DropdownMenuItem><User2 className="mr-2 h-3.5 w-3.5" /> Profile</DropdownMenuItem>
          <DropdownMenuItem>Switch role…</DropdownMenuItem>
          <DropdownMenuSeparator />
          <DropdownMenuItem disabled>Sign out (demo)</DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}

export function StatusBar() {
  return (
    <div className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-border/70 bg-card/30 px-4 py-1.5 text-[11px] text-muted-foreground">
      <span className="flex items-center gap-1.5"><StatusDot tone="warning" /> Environment: <span className="text-warning font-medium">PAPER / NON-LIVE</span></span>
      <span className="flex items-center gap-1.5"><StatusDot tone="info" /> NAV: <span className="text-foreground">Provisional · 2025-11-14</span></span>
      <span className="flex items-center gap-1.5"><StatusDot tone="positive" /> Reconciliation: <span className="text-foreground">98.4% matched · 7 open</span></span>
      <span className="flex items-center gap-1.5"><StatusDot tone="positive" /> Last sync: <span className="text-foreground num">2s ago</span></span>
      <span className="ml-auto hidden md:inline">Four-Eyes control active · Maker ≠ Checker enforced</span>
    </div>
  );
}

