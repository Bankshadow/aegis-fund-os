import { Link, useRouterState } from "@tanstack/react-router";
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
  CircleDot,
  Bot,
  RadioTower,
  PlugZap,
  CheckCheck,
  UsersRound,
} from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  useSidebar,
} from "@/components/ui/sidebar";
import { cn } from "@/lib/utils";

const NAV_GROUPS = [
  {
    label: "Command Center",
    items: [{ title: "Overview", url: "/", icon: LayoutDashboard }],
  },
  {
    label: "Trading & Research",
    items: [
      { title: "Bots & Orders", url: "/bots", icon: Bot },
      { title: "AOT Paper Grid", url: "/aot-paper-grid", icon: ChartNoAxesCombined },
      { title: "Signals", url: "/signals", icon: RadioTower },
    ],
  },
  {
    label: "Fund Operations",
    items: [
      { title: "Accounts & Custody", url: "/accounts", icon: Wallet },
      { title: "General Ledger", url: "/ledger", icon: BookOpen },
      { title: "Reconciliation", url: "/reconciliation", icon: GitCompare },
      { title: "Portfolio & NAV", url: "/portfolio", icon: LineChart },
      { title: "Risk Center", url: "/risk", icon: ShieldAlert },
    ],
  },
  {
    label: "Governance & Reporting",
    items: [
      { title: "Approvals", url: "/approvals", icon: CheckCheck },
      { title: "Reports", url: "/reports", icon: FileText },
      { title: "Audit Log", url: "/audit", icon: ScrollText },
    ],
  },
  {
    label: "Administration",
    items: [
      { title: "Integrations", url: "/integrations", icon: PlugZap },
      { title: "Access & Roles", url: "/access", icon: UsersRound },
      { title: "Settings", url: "/settings", icon: Settings },
    ],
  },
];

export function AppSidebar() {
  const { state } = useSidebar();
  const collapsed = state === "collapsed";
  const pathname = useRouterState({ select: (r) => r.location.pathname });
  const isActive = (u: string) => (u === "/" ? pathname === "/" : pathname.startsWith(u));

  return (
    <Sidebar collapsible="icon" className="border-r border-sidebar-border">
      <SidebarHeader className="border-b border-sidebar-border">
        <div className="flex items-center gap-2.5 px-1.5 py-1.5">
          <div className="grid h-8 w-8 shrink-0 place-items-center rounded-md bg-primary/15 text-primary ring-1 ring-primary/30">
            <CircleDot className="h-4 w-4" />
          </div>
          {!collapsed && (
            <div className="min-w-0">
              <div className="display text-[15px] font-semibold leading-tight tracking-tight text-sidebar-foreground">
                Aegis Fund OS
              </div>
              <div className="text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
                Ops Cockpit · v0.9
              </div>
            </div>
          )}
        </div>
      </SidebarHeader>

      <SidebarContent>
        {NAV_GROUPS.map((group) => (
          <SidebarGroup key={group.label} className="py-1.5">
            <SidebarGroupLabel>{group.label}</SidebarGroupLabel>
            <SidebarGroupContent>
              <SidebarMenu>
                {group.items.map((item) => (
                  <SidebarMenuItem key={item.url}>
                    <SidebarMenuButton asChild isActive={isActive(item.url)} tooltip={item.title}>
                      <Link to={item.url} className={cn("flex items-center gap-2.5")}>
                        <item.icon className="h-4 w-4 shrink-0" />
                        <span className="truncate">{item.title}</span>
                      </Link>
                    </SidebarMenuButton>
                  </SidebarMenuItem>
                ))}
              </SidebarMenu>
            </SidebarGroupContent>
          </SidebarGroup>
        ))}
      </SidebarContent>

      <SidebarFooter className="border-t border-sidebar-border">
        {!collapsed ? (
          <div className="px-2 py-2 text-[10px] leading-relaxed text-muted-foreground">
            <div className="font-medium text-sidebar-foreground/80">Four-Eyes Control</div>
            <div>Maker &amp; Checker required for material state changes.</div>
          </div>
        ) : (
          <div className="grid place-items-center py-2 text-muted-foreground">
            <CircleDot className="h-3.5 w-3.5" />
          </div>
        )}
      </SidebarFooter>
    </Sidebar>
  );
}
