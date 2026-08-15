import { createFileRoute } from "@tanstack/react-router";

import { AppShell, PageHeader, Panel } from "@/components/app-shell";
import { MetricCard } from "@/components/metric-card";
import { BandBadge, EntityPanel, ProvenanceNote, SourceHealth } from "@/components/news-risk";
import { getNewsRiskSnapshot } from "@/lib/news-risk.functions";

export const Route = createFileRoute("/news-assets")({
  head: () => ({ meta: [{ title: "Held Asset News · Aegis Fund OS" }] }),
  loader: () => getNewsRiskSnapshot(),
  pendingMs: 300,
  pendingComponent: () => (
    <AppShell>
      <div className="p-6 text-sm text-muted-foreground">กำลังดึงข่าวจากแหล่ง RSS…</div>
    </AppShell>
  ),
  component: AssetNewsPage,
});

function AssetNewsPage() {
  const snapshot = Route.useLoaderData();
  const assets = snapshot.assets;
  const atRisk = assets.filter((asset) => asset.band !== "CALM");
  const critical = assets.filter((asset) => asset.band === "CRITICAL");
  const quiet = assets.filter((asset) => asset.articleCount === 0);
  const worst = [...assets].sort((a, b) => b.negativePressure - a.negativePressure)[0];

  return (
    <AppShell>
      <PageHeader
        kicker="Daily Monitor 3 of 3 · Position-level news"
        title="Held Asset News"
        subtitle="ข่าวเฉพาะสินทรัพย์ที่ถือครองอยู่จริงในสมุดพอร์ต — ทั้งขาคริปโตและขาหุ้น รวมถึง stablecoin ที่ถือเป็นเงินสด"
        actions={
          <BandBadge
            band={critical.length > 0 ? "CRITICAL" : atRisk.length > 0 ? "ELEVATED" : "CALM"}
          />
        }
      />

      <div className="space-y-6 p-6">
        <ProvenanceNote generatedAt={snapshot.generatedAt} />

        <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
          <MetricCard
            demo={false}
            label="Assets held"
            value={String(assets.length)}
            sub="ดึงจากสถานะพอร์ตปัจจุบัน"
          />
          <MetricCard
            demo={false}
            label="With active news risk"
            value={`${atRisk.length} / ${assets.length}`}
            sub="ไม่อยู่ในสถานะปกติ"
            tone={atRisk.length > 0 ? "warning" : "positive"}
          />
          <MetricCard
            demo={false}
            label="Highest pressure"
            value={worst && worst.negativePressure > 0 ? worst.id : "—"}
            sub={
              worst && worst.negativePressure > 0
                ? `แรงกดด้านลบ ${worst.negativePressure.toFixed(2)}`
                : "ไม่มีแรงกดด้านลบ"
            }
            tone={worst && worst.negativePressure >= 3 ? "negative" : "default"}
          />
          <MetricCard
            demo={false}
            label="No coverage"
            value={String(quiet.length)}
            sub="ไม่มีข่าวใน 7 วัน — จุดบอด ไม่ใช่ข่าวดี"
            tone={quiet.length > 0 ? "warning" : "default"}
          />
        </div>

        <Panel title="Feed health" subtitle="ทุกแหล่งดึงแยกกัน — แหล่งที่ล่มถูกรายงาน ไม่ถูกกลบ">
          <SourceHealth sources={snapshot.sources} />
        </Panel>

        <Panel title="Asset board" subtitle="เรียงตามระดับความเสี่ยง แล้วตามแรงกดด้านลบ">
          <div className="overflow-x-auto">
            <table className="tabular w-full text-sm">
              <thead className="text-[11px] uppercase tracking-wider text-muted-foreground">
                <tr className="border-b border-border/60">
                  <th className="py-2 pr-4 text-left font-medium">Asset</th>
                  <th className="py-2 pr-4 text-left font-medium">ชื่อเต็ม</th>
                  <th className="py-2 pr-4 text-right font-medium">แรงกดลบ</th>
                  <th className="py-2 pr-4 text-right font-medium">แรงหนุนบวก</th>
                  <th className="py-2 pr-4 text-right font-medium">สุทธิ</th>
                  <th className="py-2 pr-4 text-right font-medium">ข่าว</th>
                  <th className="py-2 text-left font-medium">Band</th>
                </tr>
              </thead>
              <tbody>
                {assets.map((asset) => (
                  <tr key={asset.id} className="border-b border-border/40">
                    <td className="py-2 pr-4 font-mono font-medium">{asset.id}</td>
                    <td className="py-2 pr-4 text-muted-foreground">{asset.name}</td>
                    <td className="num py-2 pr-4 text-right text-destructive">
                      {asset.negativePressure.toFixed(2)}
                    </td>
                    <td className="num py-2 pr-4 text-right text-positive">
                      {asset.positiveSupport.toFixed(2)}
                    </td>
                    <td
                      className={`num py-2 pr-4 text-right ${asset.net < 0 ? "text-destructive" : asset.net > 0 ? "text-positive" : "text-muted-foreground"}`}
                    >
                      {asset.net > 0 ? `+${asset.net.toFixed(2)}` : asset.net.toFixed(2)}
                    </td>
                    <td className="num py-2 pr-4 text-right text-muted-foreground">
                      {asset.articleCount}
                    </td>
                    <td className="py-2">
                      <BandBadge band={asset.band} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-[11px] leading-relaxed text-muted-foreground">
            รายการนี้มาจากสัญลักษณ์ที่ถือจริงในพอร์ต โดยนับ <strong>ทั้งสองขาของคู่เทรด</strong> —
            การนั่งถือ USDT คือการถือ Tether และข่าว depeg คือสิ่งที่กระดานนี้มีไว้ดักโดยเฉพาะ ·
            คอลัมน์ &ldquo;สุทธิ&rdquo; เป็นข้อมูลประกอบเท่านั้น ระดับความเสี่ยงไม่ได้คิดจากค่าสุทธิ
          </p>
        </Panel>

        <div className="space-y-4">
          <h2 className="text-sm font-semibold tracking-tight">รายละเอียดข่าวรายสินทรัพย์</h2>
          {assets.map((asset) => (
            <EntityPanel
              key={asset.id}
              entity={asset}
              kicker={`${asset.name} · ถือครองอยู่ในพอร์ต`}
            />
          ))}
        </div>
      </div>
    </AppShell>
  );
}
