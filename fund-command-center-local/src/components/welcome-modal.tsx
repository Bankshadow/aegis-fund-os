import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { ShieldCheck, Users, TriangleAlert } from "lucide-react";

const STORAGE_KEY = "aegis:welcome:dismissed";

export function WelcomeModal() {
  const [open, setOpen] = useState(false);
  useEffect(() => {
    try {
      const v = window.localStorage.getItem(STORAGE_KEY);
      if (!v) setOpen(true);
    } catch { /* ignore */ }
  }, []);
  const dismiss = () => {
    try { window.localStorage.setItem(STORAGE_KEY, "1"); } catch {/**/}
    setOpen(false);
  };
  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogContent className="max-w-lg">
        <DialogHeader>
          <div className="mb-2 inline-flex w-fit items-center gap-2 rounded-sm border border-warning/40 bg-warning/10 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-warning">
            <span className="h-1.5 w-1.5 rounded-full bg-warning" /> Paper / Non-Live prototype
          </div>
          <DialogTitle className="display text-2xl">Welcome to Aegis Fund OS</DialogTitle>
          <DialogDescription>
            An operations cockpit for institutional private fund research, paper-trading operations,
            portfolio accounting, and investor-grade reporting. This build is a prototype — <em>no live
            execution, no third-party capital handling, no regulatory approval implied.</em>
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-3 text-sm">
          <div className="flex items-start gap-3 rounded-md border border-border/70 bg-card/40 p-3">
            <TriangleAlert className="mt-0.5 h-4 w-4 text-warning shrink-0" />
            <div>
              <div className="font-medium">Demo / Paper mode</div>
              <div className="text-muted-foreground text-xs">All values are seeded, all adapters are paper/testnet/sandbox. No live orders are ever transmitted.</div>
            </div>
          </div>
          <div className="flex items-start gap-3 rounded-md border border-border/70 bg-card/40 p-3">
            <Users className="mt-0.5 h-4 w-4 text-info shrink-0" />
            <div>
              <div className="font-medium">Four-Eyes control</div>
              <div className="text-muted-foreground text-xs">Material state changes (NAV lock, paper-order approval, limit updates) require a checker different from the maker.</div>
            </div>
          </div>
          <div className="flex items-start gap-3 rounded-md border border-border/70 bg-card/40 p-3">
            <ShieldCheck className="mt-0.5 h-4 w-4 text-positive shrink-0" />
            <div>
              <div className="font-medium">Audit-first design</div>
              <div className="text-muted-foreground text-xs">Every event is hashed, timestamped, and reproducible. Read-only auditor role is included.</div>
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={dismiss}>Explore later</Button>
          <Button onClick={dismiss}>Enter cockpit</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

