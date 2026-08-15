import { ExternalLink, Rss, TriangleAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { StatusDot } from "@/components/demo-tag";
import { cn } from "@/lib/utils";
import type { EntityRisk, RiskBand, ScoredArticle, SourceStatus } from "@/lib/news-risk";

const BAND_LABEL: Record<RiskBand, string> = {
  CRITICAL: "วิกฤต",
  ELEVATED: "สูง",
  WATCH: "เฝ้าระวัง",
  CALM: "ปกติ",
};

const BAND_CLASS: Record<RiskBand, string> = {
  CRITICAL: "border-destructive/60 bg-destructive/15 text-destructive",
  ELEVATED: "border-warning/60 bg-warning/15 text-warning",
  WATCH: "border-info/50 bg-info/10 text-info",
  CALM: "border-border/60 bg-card/60 text-muted-foreground",
};

export function BandBadge({ band, className }: { band: RiskBand; className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-sm border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.12em]",
        BAND_CLASS[band],
        className,
      )}
    >
      {band} · {BAND_LABEL[band]}
    </span>
  );
}

/** Signed tilt of one article: negative reads as pressure on the venue/asset. */
export function ScorePill({ score }: { score: number }) {
  const tone =
    score <= -2
      ? "text-destructive"
      : score < 0
        ? "text-warning"
        : score > 0
          ? "text-positive"
          : "text-muted-foreground";
  return (
    <span className={cn("num text-xs font-semibold", tone)}>{score > 0 ? `+${score}` : score}</span>
  );
}

export function SignalChips({ signals }: { signals: ScoredArticle["signals"] }) {
  if (signals.length === 0)
    return <span className="text-[10px] text-muted-foreground">ไม่เข้าเงื่อนไขคีย์เวิร์ดใด</span>;
  return (
    <div className="flex flex-wrap gap-1">
      {signals.map((signal) => (
        <Badge
          key={signal.id}
          variant="outline"
          className={cn(
            "text-[10px] font-normal",
            signal.severe
              ? "border-destructive/50 text-destructive"
              : signal.weight < 0
                ? "border-warning/50 text-warning"
                : "border-positive/50 text-positive",
          )}
        >
          {signal.label} {signal.weight > 0 ? `+${signal.weight}` : signal.weight}
        </Badge>
      ))}
    </div>
  );
}

const relativeTime = (iso: string | null): string => {
  if (!iso) return "ไม่ระบุเวลา";
  const minutes = Math.round((Date.now() - Date.parse(iso)) / 60_000);
  if (!Number.isFinite(minutes)) return "ไม่ระบุเวลา";
  // Statuspage feeds date scheduled changes in the future — say so rather than
  // rounding them to "just now".
  if (minutes < -60) {
    const hoursAhead = Math.round(-minutes / 60);
    return hoursAhead < 48 ? `อีก ${hoursAhead} ชม.` : `อีก ${Math.round(hoursAhead / 24)} วัน`;
  }
  if (minutes < 60) return `${Math.max(0, minutes)} นาทีที่แล้ว`;
  const hours = Math.round(minutes / 60);
  if (hours < 48) return `${hours} ชม.ที่แล้ว`;
  return `${Math.round(hours / 24)} วันที่แล้ว`;
};

export function ArticleRow({ article }: { article: ScoredArticle }) {
  return (
    <li className="border-b border-border/40 py-2.5 last:border-0">
      <div className="flex items-start gap-3">
        <ScorePill score={article.score} />
        <div className="min-w-0 flex-1">
          <a
            href={article.link || undefined}
            target="_blank"
            rel="noreferrer noopener"
            className="group inline-flex items-start gap-1.5 text-sm font-medium leading-snug hover:text-primary"
          >
            <span className="min-w-0">{article.title}</span>
            {article.link && (
              <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 opacity-0 transition-opacity group-hover:opacity-70" />
            )}
          </a>
          <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-muted-foreground">
            <span>{article.sourceLabel}</span>
            <span>·</span>
            <span>{relativeTime(article.publishedAt)}</span>
            <span>·</span>
            <span className="num">น้ำหนักตามความสด {article.decay.toFixed(2)}×</span>
            {article.scheduled && (
              <Badge variant="outline" className="border-info/50 text-[10px] font-normal text-info">
                กำหนดล่วงหน้า
              </Badge>
            )}
            {article.narrowScope && (
              <Badge variant="outline" className="text-[10px] font-normal">
                กระทบเฉพาะบางเหรียญ/บางเขต
              </Badge>
            )}
          </div>
          <div className="mt-1.5">
            <SignalChips signals={article.signals} />
          </div>
        </div>
      </div>
    </li>
  );
}

export function EntityPanel({ entity, kicker }: { entity: EntityRisk; kicker: string }) {
  return (
    <section className="rounded-md border border-border/70 bg-card/40">
      <header className="flex flex-wrap items-center justify-between gap-2 border-b border-border/60 px-4 py-2.5">
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold tracking-tight">{entity.name}</span>
            {entity.held ? (
              <Badge variant="outline" className="border-primary/50 text-[10px] text-primary">
                ถือครอง
              </Badge>
            ) : (
              entity.watched && (
                <Badge variant="outline" className="border-info/50 text-[10px] text-info">
                  ติดตามประจำ
                </Badge>
              )
            )}
            {entity.rank !== null && (
              <span className="text-[10px] text-muted-foreground">#{entity.rank}</span>
            )}
          </div>
          <div className="mt-0.5 text-[11px] text-muted-foreground">{kicker}</div>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-right text-[11px] text-muted-foreground">
            <div>
              ลบ{" "}
              <span className="num font-semibold text-destructive">
                {entity.negativePressure.toFixed(2)}
              </span>{" "}
              · บวก{" "}
              <span className="num font-semibold text-positive">
                {entity.positiveSupport.toFixed(2)}
              </span>
            </div>
            <div className="num">{entity.articleCount} ข่าวใน 7 วัน</div>
          </div>
          <BandBadge band={entity.band} />
        </div>
      </header>
      <div className="px-4 py-1">
        {entity.articles.length === 0 ? (
          <p className="py-3 text-xs text-muted-foreground">
            ไม่มีข่าวที่จับคู่ได้ใน 7 วันที่ผ่านมา
          </p>
        ) : (
          <ul>
            {entity.articles.map((article) => (
              <ArticleRow key={`${entity.id}-${article.link || article.title}`} article={article} />
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}

export function SourceHealth({ sources }: { sources: SourceStatus[] }) {
  const failed = sources.filter((source) => source.status === "failed");
  return (
    <div className="space-y-2">
      {failed.length > 0 && (
        <div className="flex items-start gap-2 rounded-md border border-warning/40 bg-warning/10 p-2.5 text-xs text-warning">
          <TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
          <span>
            {failed.length} จาก {sources.length} แหล่งข่าวดึงไม่สำเร็จ —
            คะแนนด้านล่างคำนวณจากแหล่งที่เหลือเท่านั้น อย่าอ่านว่า &ldquo;ไม่มีข่าว&rdquo;
          </span>
        </div>
      )}
      <ul className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-4">
        {sources.map((source) => (
          <li
            key={source.id}
            className="flex items-center gap-2 rounded-md border border-border/60 bg-background/40 px-2.5 py-1.5 text-[11px]"
          >
            <StatusDot tone={source.status === "ok" ? "positive" : "destructive"} />
            <Rss className="h-3 w-3 text-muted-foreground" />
            <span className="min-w-0 flex-1 truncate">{source.label}</span>
            <span className="num text-muted-foreground">
              {source.status === "ok" ? source.itemCount : (source.error ?? "failed")}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * The news is live; the holdings overlay is the prototype's paper book. Saying so
 * on every news board keeps the two from being read as one verified whole.
 */
export function ProvenanceNote({ generatedAt }: { generatedAt: string }) {
  return (
    <p className="text-[11px] leading-relaxed text-muted-foreground">
      ข่าว = RSS สาธารณะแบบสด · การถือครอง = สมุดพอร์ต paper/testnet ของต้นแบบนี้ (ไม่ใช่ custody
      จริง) · คะแนนมาจากกฎคีย์เวิร์ดที่กำหนดไว้ล่วงหน้า ไม่ใช่ความเห็นของโมเดล
      และไม่ใช่คำแนะนำการลงทุน · ดึงข้อมูลเมื่อ{" "}
      <span className="num">{new Date(generatedAt).toLocaleString("th-TH")}</span> (แคช 10 นาที)
    </p>
  );
}
