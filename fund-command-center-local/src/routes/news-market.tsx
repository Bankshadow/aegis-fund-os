import { createFileRoute } from "@tanstack/react-router";
import { ExternalLink, Flame } from "lucide-react";

import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { ProvenanceNote, ScorePill, SignalChips, SourceHealth } from "@/components/news-risk";
import { Badge } from "@/components/ui/badge";
import { EXCHANGE_REGISTRY } from "@/lib/news-risk";
import { getNewsRiskSnapshot } from "@/lib/news-risk.functions";

export const Route = createFileRoute("/news-market")({
  head: () => ({ meta: [{ title: "Market Pulse · Aegis Fund OS" }] }),
  loader: () => getNewsRiskSnapshot(),
  pendingMs: 300,
  pendingComponent: () => (
    <AppShell>
      <div className="p-6 text-sm text-muted-foreground">กำลังดึงข่าวจากแหล่ง RSS…</div>
    </AppShell>
  ),
  component: MarketPulsePage,
});

const EXCHANGE_NAME = new Map(EXCHANGE_REGISTRY.map((entry) => [entry.id, entry.name]));

function MarketPulsePage() {
  const snapshot = Route.useLoaderData();

  return (
    <AppShell>
      <PageHeader
        kicker="Supplementary · Cross-source story heat"
        title="Market Pulse"
        subtitle="ข่าวกระแสแรงทั่วไป จัดอันดับจากจำนวนสำนักข่าวที่รายงานเรื่องเดียวกัน ไม่ใช่จากความรุนแรงของข่าว"
      />

      <div className="space-y-6 p-6">
        <ProvenanceNote generatedAt={snapshot.generatedAt} />

        <Panel title="Feed health" subtitle="ทุกแหล่งดึงแยกกัน — แหล่งที่ล่มถูกรายงาน ไม่ถูกกลบ">
          <SourceHealth sources={snapshot.sources} />
        </Panel>

        <Panel
          title="Trending stories"
          subtitle="รวมข่าวหัวข้อใกล้เคียงกันเป็นเรื่องเดียว แล้วเรียงตามค่าความร้อน"
        >
          {snapshot.trending.length === 0 ? (
            <p className="py-3 text-sm text-muted-foreground">
              ยังไม่มีข่าวที่ดึงได้ — ดูสถานะแหล่งข่าวด้านบน
            </p>
          ) : (
            <ol className="space-y-3">
              {snapshot.trending.map((story, index) => (
                <li
                  key={story.key}
                  className="flex items-start gap-3 border-b border-border/40 pb-3 last:border-0 last:pb-0"
                >
                  <span className="num w-6 shrink-0 pt-0.5 text-right text-sm font-semibold text-muted-foreground">
                    {index + 1}
                  </span>
                  <div className="min-w-0 flex-1">
                    <a
                      href={story.link || undefined}
                      target="_blank"
                      rel="noreferrer noopener"
                      className="group inline-flex items-start gap-1.5 text-sm font-medium leading-snug hover:text-primary"
                    >
                      <span className="min-w-0">{story.title}</span>
                      {story.link && (
                        <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-70" />
                      )}
                    </a>
                    <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
                      <span className="inline-flex items-center gap-1 text-warning">
                        <Flame className="h-3 w-3" />
                        <span className="num font-semibold">{story.heat.toFixed(2)}</span>
                      </span>
                      <span>·</span>
                      <span>{story.sourceLabels.join(", ")}</span>
                      {story.sourceLabels.length > 1 && (
                        <Badge variant="outline" className="border-info/50 text-[10px] text-info">
                          {story.sourceLabels.length} สำนักข่าว
                        </Badge>
                      )}
                    </div>
                    <div className="mt-1.5 flex flex-wrap items-center gap-2">
                      <ScorePill score={story.score} />
                      <SignalChips signals={story.signals} />
                    </div>
                    {(story.exchangeIds.length > 0 || story.assetSymbols.length > 0) && (
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {story.exchangeIds.map((id) => (
                          <Badge key={id} variant="outline" className="text-[10px] font-normal">
                            {EXCHANGE_NAME.get(id) ?? id}
                          </Badge>
                        ))}
                        {story.assetSymbols.map((symbol) => (
                          <Badge
                            key={symbol}
                            variant="outline"
                            className="font-mono text-[10px] font-normal"
                          >
                            {symbol}
                          </Badge>
                        ))}
                      </div>
                    )}
                  </div>
                </li>
              ))}
            </ol>
          )}
          <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
            ค่าความร้อน = ความสดของข่าว × (2 × จำนวนสำนักข่าวที่รายงาน + ความแรงของคะแนน) — วัด
            <strong> เสียงดังแค่ไหน</strong> ไม่ใช่ <strong>ร้ายแรงแค่ไหน</strong>{" "}
            การตัดสินความเสี่ยงให้ดูที่กระดาน Exchange และ Assets เท่านั้น
          </p>
        </Panel>
      </div>
    </AppShell>
  );
}
