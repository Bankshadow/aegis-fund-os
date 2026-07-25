import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";

/**
 * Shell for the student-facing Walk-Forward Lab pages.
 *
 * Deliberately NOT AppShell: that one is a fund operations cockpit and wraps every
 * page in an institutional welcome modal ("Enter cockpit"), a fund identity header
 * and a NAV / reconciliation / four-eyes status strip. Testing the lab as a student
 * showed that chrome is not just noise — it implies a real fund with real money
 * sitting behind a teaching page. Students get navigation, the content, and an
 * unambiguous "this is teaching material, nothing is live" line.
 */
const LINKS = [
  { to: "/walk-forward", label: "ผลราย fold", search: { variant: "baseline" as const, cost: "thai" as const } },
  { to: "/walk-forward-compare", label: "เปรียบเทียบกลไก" },
  { to: "/walk-forward-overfit", label: "บทเรียน overfitting" },
];

export function EducationShell({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen bg-background">
      <header className="border-b border-border/70 bg-card/30">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <div className="min-w-0">
            <div className="text-sm font-semibold tracking-tight">Walk-Forward Lab</div>
            <div className="text-[11px] text-muted-foreground">เครื่องมือเรียนรู้ — ไม่มีการเทรดจริง ไม่ใช่คำแนะนำการลงทุน</div>
          </div>
          <nav className="flex flex-wrap gap-1">
            {LINKS.map((link) => (
              <Link
                key={link.to}
                to={link.to}
                search={link.search as never}
                className="rounded px-2.5 py-1.5 text-xs text-muted-foreground hover:bg-accent hover:text-accent-foreground [&.active]:bg-primary [&.active]:text-primary-foreground"
                // Exact, or "/walk-forward" would also light up on the -compare and
                // -overfit routes, since it is a prefix of both.
                activeOptions={{ exact: true, includeSearch: false }}
              >
                {link.label}
              </Link>
            ))}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl min-w-0 overflow-x-hidden">{children}</main>
      <footer className="border-t border-border/70 px-4 py-3 text-[11px] text-muted-foreground">
        สื่อการเรียนรู้เท่านั้น · ผลย้อนหลังไม่รับประกันอนาคต · ไม่มีการส่งคำสั่งซื้อขายจริงจากหน้านี้
      </footer>
    </div>
  );
}
