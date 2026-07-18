import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
} from "@/components/ui/command";
import {
  LayoutDashboard,
  Wallet,
  BookOpen,
  GitCompare,
  LineChart,
  ShieldAlert,
  FileText,
  ScrollText,
  ChartNoAxesCombined,
  Settings,
  Lock,
  Search,
  Bot,
  RadioTower,
  PlugZap,
  CheckCheck,
  UsersRound,
} from "lucide-react";

const groups = [
  {
    heading: "Command Center",
    items: [{ icon: LayoutDashboard, label: "Overview", to: "/" }],
  },
  {
    heading: "Trading & Research",
    items: [
      { icon: Bot, label: "Bots & Orders", to: "/bots" },
      { icon: ChartNoAxesCombined, label: "AOT Paper Grid", to: "/aot-paper-grid" },
      { icon: RadioTower, label: "Signals", to: "/signals" },
    ],
  },
  {
    heading: "Fund Operations",
    items: [
      { icon: Wallet, label: "Accounts & Custody", to: "/accounts" },
      { icon: BookOpen, label: "General Ledger", to: "/ledger" },
      { icon: GitCompare, label: "Reconciliation", to: "/reconciliation" },
      { icon: LineChart, label: "Portfolio & NAV", to: "/portfolio" },
      { icon: ShieldAlert, label: "Risk Center", to: "/risk" },
    ],
  },
  {
    heading: "Governance & Reporting",
    items: [
      { icon: CheckCheck, label: "Approvals", to: "/approvals" },
      { icon: FileText, label: "Reports", to: "/reports" },
      { icon: ScrollText, label: "Audit Log", to: "/audit" },
    ],
  },
  {
    heading: "Administration",
    items: [
      { icon: PlugZap, label: "Integrations", to: "/integrations" },
      { icon: UsersRound, label: "Access & Roles", to: "/access" },
      { icon: Settings, label: "Settings", to: "/settings" },
    ],
  },
];

const actions = [
  { icon: Lock, label: "Attempt NAV lock (demo)", hint: "Portfolio & NAV" },
  { icon: Search, label: "Find break by ID…", hint: "Reconciliation" },
  { icon: FileText, label: "Generate Monthly Factsheet (demo)", hint: "Reports" },
];

export function CommandPalette({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (b: boolean) => void;
}) {
  const nav = useNavigate();
  const [, setTick] = useState(0);
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        onOpenChange(!open);
        setTick((t) => t + 1);
      }
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, [open, onOpenChange]);

  return (
    <CommandDialog open={open} onOpenChange={onOpenChange}>
      <CommandInput placeholder="Search accounts, tickers, events, reports… (demo)" />
      <CommandList>
        <CommandEmpty>No results.</CommandEmpty>
        {groups.map((group, index) => (
          <div key={group.heading}>
            {index > 0 && <CommandSeparator />}
            <CommandGroup heading={group.heading}>
              {group.items.map((it) => (
                <CommandItem
                  key={it.to}
                  onSelect={() => {
                    onOpenChange(false);
                    nav({ to: it.to });
                  }}
                >
                  <it.icon className="mr-2 h-3.5 w-3.5" />
                  {it.label}
                </CommandItem>
              ))}
            </CommandGroup>
          </div>
        ))}
        <CommandSeparator />
        <CommandGroup heading="Actions (demo)">
          {actions.map((a) => (
            <CommandItem key={a.label} onSelect={() => onOpenChange(false)}>
              <a.icon className="mr-2 h-3.5 w-3.5" />
              <span>{a.label}</span>
              <span className="ml-auto text-[10px] text-muted-foreground">{a.hint}</span>
            </CommandItem>
          ))}
        </CommandGroup>
      </CommandList>
    </CommandDialog>
  );
}
