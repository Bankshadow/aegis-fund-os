import { createFileRoute } from "@tanstack/react-router";

import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { BandBadge, EntityPanel, ProvenanceNote, SourceHealth } from "@/components/news-risk";
import { Badge } from "@/components/ui/badge";
import { getNewsRiskSnapshot } from "@/lib/news-risk.functions";

export const Route = createFileRoute("/news-exchanges")({
  head: () => ({ meta: [{ title: "Exchange News Risk · Aegis Fund OS" }] }),
  loader: () => getNewsRiskSnapshot(),
  pendingMs: 300,
  pendingComponent: () => (
    <AppShell>
      <div className="p-6 text-sm text-muted-foreground">กำลังดึงข่าวจากแหล่ง RSS…</div>
    </AppShell>
  ),
  component: ExchangeNewsPage,
});

function ExchangeNewsPage() {
  const snapshot = Route.useLoaderData();
  const held = snapshot.exchanges.filter((exchange) => exchange.held);
  const watchlist = snapshot.exchanges.filter((exchange) => !exchange.held);
  const critical = snapshot.exchanges.filter((exchange) => exchange.band === "CRITICAL");
  const worst = [...snapshot.exchanges].sort((a, b) => b.negativePressure - a.negativePressure)[0];
  const okSources = snapshot.sources.filter((source) => source.status === "ok").length;

  return (
    <AppShell>
      <PageHeader
        kicker="Daily Monitor 2 of 3 · Exchange counterparty news"
        title="Exchange News Risk"
        subtitle="ข่าวที่กระทบ exchange ที่เราถือ asset อยู่ และ Top 10 ทั้งตลาด — คะแนนบวก/ลบจากกฎคีย์เวิร์ดแบบตายตัว"
        actions={
          <BandBadge
            band={
              critical.length > 0
                ? "CRITICAL"
                : held.some((h) => h.band !== "CALM")
                  ? "ELEVATED"
                  : "CALM"
            }
          />
        }
      />

      <div className="space-y-6 p-6">
        <ProvenanceNote generatedAt={snapshot.generatedAt} />

        <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5">
          <MetricCard
            demo={false}
            label="Held venues at risk"
            value={`${snapshot.totals.heldExchangesAtRisk} / ${held.length}`}
            sub="ที่ไม่อยู่ในสถานะปกติ"
            tone={snapshot.totals.heldExchangesAtRisk > 0 ? "warning" : "positive"}
          />
          <MetricCard
            demo={false}
            label="Critical venues"
            value={String(critical.length)}
            sub="มีข่าวระดับคุกคาม custody"
            tone={critical.length > 0 ? "negative" : "positive"}
          />
          <MetricCard
            demo={false}
            label="Highest pressure"
            value={worst && worst.negativePressure > 0 ? worst.name : "—"}
            sub={
              worst && worst.negativePressure > 0
                ? `แรงกดด้านลบ ${worst.negativePressure.toFixed(2)}`
                : "ไม่มีแรงกดด้านลบ"
            }
            tone={worst && worst.negativePressure >= 3 ? "negative" : "default"}
          />
          <MetricCard
            demo={false}
            label="Articles scored"
            value={String(snapshot.totals.scoredArticles)}
            sub="ภายใน 7 วันล่าสุด"
          />
          <MetricCard
            demo={false}
            label="Feeds live"
            value={`${okSources} / ${snapshot.sources.length}`}
            sub="แหล่งข่าวที่ดึงสำเร็จ"
            tone={okSources === snapshot.sources.length ? "positive" : "warning"}
          />
        </div>

        <Panel title="Feed health" subtitle="ทุกแหล่งดึงแยกกัน — แหล่งที่ล่มถูกรายงาน ไม่ถูกกลบ">
          <SourceHealth sources={snapshot.sources} />
        </Panel>

        <Panel
          title="Venue board"
          subtitle="เรียงตาม: ที่เราถือครองก่อน → ระดับความเสี่ยง → ที่ติดตามประจำ → อันดับ Top 10"
        >
          <div className="overflow-x-auto">
            <table className="tabular w-full text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border/60">
                  <th className="py-2 pr-4 text-left font-medium">Venue</th>
                  <th className="py-2 pr-4 text-left font-medium">Rank</th>
                  <th className="py-2 pr-4 text-left font-medium">Exposure</th>
                  <th className="py-2 pr-4 text-right font-medium">แรงกดลบ</th>
                  <th className="py-2 pr-4 text-right font-medium">แรงหนุนบวก</th>
                  <th className="py-2 pr-4 text-left font-medium w-[22%]">Tilt</th>
                  <th className="py-2 pr-4 text-right font-medium">ข่าว</th>
                  <th className="py-2 text-left font-medium">Band</th>
                </tr>
              </thead>
              <tbody>
                {snapshot.exchanges.map((exchange) => {
                  const span = Math.max(exchange.negativePressure, exchange.positiveSupport, 1);
                  return (
                    <tr key={exchange.id} className="border-b border-border/40">
                      <td className="py-2 pr-4 font-medium">{exchange.name}</td>
                      <td className="py-2 pr-4 text-muted-foreground">{exchange.rank ?? "—"}</td>
                      <td className="py-2 pr-4">
                        {exchange.held ? (
                          <Badge
                            variant="outline"
                            className="border-primary/50 text-[10px] text-primary"
                          >
                            ถือครอง
                          </Badge>
                        ) : exchange.watched ? (
                          <Badge variant="outline" className="border-info/50 text-[10px] text-info">
                            ติดตามประจำ
                          </Badge>
                        ) : (
                          <span className="text-[11px] text-muted-foreground">เฝ้าดู</span>
                        )}
                      </td>
                      <td className="num py-2 pr-4 text-right text-destructive">
                        {exchange.negativePressure.toFixed(2)}
                      </td>
                      <td className="num py-2 pr-4 text-right text-positive">
                        {exchange.positiveSupport.toFixed(2)}
                      </td>
                      <td className="py-2 pr-4">
                        <div className="flex h-1.5 items-center overflow-hidden rounded-full bg-accent/60">
                          <div
                            className="h-full bg-destructive"
                            style={{ width: `${(exchange.negativePressure / span) * 50}%` }}
                          />
                          <div
                            className="h-full bg-positive"
                            style={{ width: `${(exchange.positiveSupport / span) * 50}%` }}
                          />
                        </div>
                      </td>
                      <td className="num py-2 pr-4 text-right text-muted-foreground">
                        {exchange.articleCount}
                      </td>
                      <td className="py-2">
                        <BandBadge band={exchange.band} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
            ระดับความเสี่ยงคิดจาก <strong>แรงกดด้านลบเท่านั้น</strong> — ข่าวดีไม่หักล้างข่าวร้าย
            เพราะ proof-of-reserves ในสัปดาห์เดียวกับการระงับถอนเงินไม่ได้ทำให้การระงับถอนเงินหายไป
            · ข่าวใหม่มีน้ำหนักมากกว่า (ครึ่งชีวิต 48 ชม.) · ข่าวระดับ severe (แฮก / ระงับถอน /
            ล้มละลาย / depeg) ดันระดับขึ้นทันทีอย่างน้อย ELEVATED
          </p>
        </Panel>

        <div className="space-y-4">
          <h2 className="text-sm font-semibold tracking-tight">Venues we hold assets on</h2>
          {held.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              ไม่มี venue ที่มียอดคงเหลือในสมุดพอร์ตต้นแบบ
            </p>
          ) : (
            held.map((exchange) => (
              <EntityPanel
                key={exchange.id}
                entity={exchange}
                kicker="Counterparty ที่มียอดคงเหลือ (paper/testnet)"
              />
            ))
          )}
        </div>

        <div className="space-y-4">
          <h2 className="text-sm font-semibold tracking-tight">Watchlist</h2>
          {/* A watched venue keeps its panel even at zero articles — for a venue
              you run bots on, "nothing happened" is the answer you came for. */}
          {watchlist
            .filter((exchange) => exchange.watched || exchange.articleCount > 0)
            .map((exchange) => (
              <EntityPanel
                key={exchange.id}
                entity={exchange}
                kicker={
                  exchange.watched
                    ? "ติดตามประจำ — ไม่ได้ถือครองในสมุดพอร์ตต้นแบบ"
                    : "ไม่ได้ถือครอง — ดูเพื่อจับสัญญาณลามทั้งตลาด"
                }
              />
            ))}
        </div>
      </div>
    </AppShell>
  );
}
