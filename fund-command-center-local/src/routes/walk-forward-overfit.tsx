import { createFileRoute, Link } from "@tanstack/react-router";
import { PageHeader, Panel } from "@/components/app-shell";
import { EducationShell } from "@/components/education-shell";
import { WalkForwardGlossary } from "@/components/walk-forward-glossary";
import { Button } from "@/components/ui/button";
import { getOverfitView } from "@/lib/walk-forward.functions";

export const Route = createFileRoute("/walk-forward-overfit")({
  head: () => ({ meta: [{ title: "Overfitting Lab · Walk-Forward Lab" }] }),
  loader: async () => getOverfitView(),
  pendingMs: 200,
  pendingComponent: () => (
    <EducationShell>
      <div className="p-6 text-sm text-muted-foreground">
        กำลังให้คะแนนรูปแบบ grid ทุกตัวเลือก ทั้งในช่วงที่ใช้ตั้งค่าและช่วงที่ยังไม่เคยเห็น… (ไม่กี่วินาที)
      </div>
    </EducationShell>
  ),
  component: OverfitLab,
});

const signed = (value: number, digits = 1) => `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
const tone = (value: number) => (value >= 0 ? "text-positive" : "text-destructive");

function OverfitLab() {
  const { folds, summary } = Route.useLoaderData();
  const pickPct = (summary.pickWasBest / summary.folds) * 100;
  const randomPct = 100 / summary.candidatesPerFold;

  return (
    <EducationShell>
      <PageHeader
        kicker="EDUCATION · READ-ONLY RESEARCH · NO LIVE ORDER"
        title="บทเรียน overfitting — จูนจากอดีตแล้วใช้ได้จริงกับอนาคตไหม?"
        subtitle="ทุกช่วงทดสอบ ระบบเลือกรูปแบบ grid ที่ดีที่สุดจากข้อมูล 2 ปีแรกเท่านั้น (มี 6 แบบให้เลือก) แล้ววัดผลจริงในปีถัดไปที่ยังไม่เคยเห็น คำถามเดียว: การเลือกจากอดีต ทำนายอนาคตได้ไหม"
      />
      <div className="space-y-6 p-6">
        <WalkForwardGlossary />

        <Panel title="คำตอบ" subtitle="เทียบกับการสุ่มเลือกแบบไม่ดูข้อมูลเลย">
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-md border p-4">
              <div className="text-xs text-muted-foreground">ตัวที่ชนะ in-sample เป็นตัวที่ชนะ out-of-sample ด้วย</div>
              <div className="mt-1 text-3xl font-semibold">
                {summary.pickWasBest}/{summary.folds}
                <span className="ml-2 text-lg text-muted-foreground">({pickPct.toFixed(1)}%)</span>
              </div>
              <div className="mt-1 text-xs text-muted-foreground">
                สุ่มเลือกจะได้ ~{randomPct.toFixed(1)}% ({summary.randomWouldBe.toFixed(1)}/{summary.folds})
              </div>
            </div>
            <div className="rounded-md border p-4">
              <div className="text-xs text-muted-foreground">อันดับ out-of-sample เฉลี่ยของตัวที่เลือก (จาก {summary.candidatesPerFold})</div>
              <div className="mt-1 text-3xl font-semibold">{summary.meanPickRank.toFixed(2)}</div>
              <div className="mt-1 text-xs text-muted-foreground">สุ่มเลือกจะได้ {summary.randomMeanRank.toFixed(2)}</div>
            </div>
          </div>
          <div className="mt-4 rounded-md border border-destructive/40 p-4">
            <div className="font-semibold text-destructive">การเลือกจาก in-sample ≈ การสุ่ม</div>
            <p className="mt-1 text-sm text-muted-foreground">
              ตัวเลขสองช่องบนแทบเท่ากับค่าที่ได้จากการสุ่มล้วน แปลว่าคะแนน in-sample <strong>ไม่มีข้อมูล</strong>
              เกี่ยวกับผลในอนาคตเลยบนข้อมูลชุดนี้ ใครที่จูนพารามิเตอร์จนกราฟย้อนหลังสวย กำลังวัดเสียงรบกวน ไม่ใช่ edge
            </p>
          </div>
        </Panel>

        <Panel title="แล้วถ้าเลือกถูกทุกครั้งล่ะ?" subtitle="เพดานที่เป็นไปไม่ได้ — สมมติรู้อนาคตแล้วเลือกตัวที่ดีที่สุดเสมอ">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-md border p-4">
              <div className="text-xs text-muted-foreground">เลือกจาก in-sample (ของจริง)</div>
              <div className={`mt-1 text-2xl font-semibold ${tone(summary.meanPickOos)}`}>{signed(summary.meanPickOos, 2)}</div>
            </div>
            <div className="rounded-md border p-4">
              <div className="text-xs text-muted-foreground">เฉลี่ยทุกตัวเลือก (เหมือนสุ่ม)</div>
              <div className={`mt-1 text-2xl font-semibold ${tone(summary.meanCandidateOos)}`}>
                {signed(summary.meanCandidateOos, 2)}
              </div>
            </div>
            <div className="rounded-md border p-4">
              <div className="text-xs text-muted-foreground">ดีที่สุดแบบรู้อนาคต (เพดาน)</div>
              <div className={`mt-1 text-2xl font-semibold ${tone(summary.meanHindsightBestOos)}`}>
                {signed(summary.meanHindsightBestOos, 2)}
              </div>
            </div>
          </div>
          <p className="mt-3 text-sm text-muted-foreground">
            ประเด็นสำคัญ: แม้แต่ช่องขวาสุด — ซึ่งต้องรู้อนาคตถึงจะทำได้ — ก็ยัง<strong>ติดลบหนัก</strong>
            แปลว่าปัญหาไม่ได้อยู่ที่ "เลือกรูปแบบ grid ผิด" ต่อให้จูนรูปแบบให้ดีขึ้นก็แก้อะไรไม่ได้ เพราะตัวกลไกไม่มีความได้เปรียบ
            ตั้งแต่ต้น (robust ต้อง &gt; 0 ถึงจะผ่านเกณฑ์)
          </p>
        </Panel>

        <Panel
          title="ราย fold: อันดับ in-sample vs อันดับจริง"
          subtitle="แถบไฮไลต์คือตัวที่ระบบเลือก (ชนะในช่วงตั้งค่า) · ตัวเลขคือคะแนนรวมในช่วงจริงและอันดับที่ได้จริง"
        >
          <div className="overflow-x-auto">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="text-left text-xs uppercase text-muted-foreground">
                  <th className="p-2">Fold</th>
                  <th className="p-2">OOS range</th>
                  <th className="p-2">ตัวที่เลือก</th>
                  <th className="p-2">อันดับจริง</th>
                  <th className="p-2">ตัวเลือกทั้งหมด (คะแนนจริง · อันดับ)</th>
                </tr>
              </thead>
              <tbody>
                {folds.map((fold) => {
                  const picked = fold.candidates.find((c) => c.selected);
                  return (
                    <tr className="border-t align-top" key={fold.index}>
                      <td className="p-2">{fold.index}</td>
                      <td className="p-2 font-mono text-xs">{fold.oosRange.join(" → ")}</td>
                      <td className="p-2 font-mono text-xs">{picked?.label}</td>
                      <td className={`p-2 font-mono ${fold.pickOosRank === 1 ? "text-positive" : "text-destructive"}`}>
                        {fold.pickOosRank}/{fold.candidates.length}
                      </td>
                      <td className="p-2">
                        <div className="flex flex-wrap gap-1">
                          {fold.candidates.map((candidate) => (
                            <span
                              className={`rounded border px-1.5 py-0.5 font-mono text-xs ${
                                candidate.selected ? "border-primary bg-primary/10" : "text-muted-foreground"
                              }`}
                              key={candidate.label}
                            >
                              {candidate.label} {signed(candidate.oosRobust, 0)} · #{candidate.oosRank}
                            </span>
                          ))}
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </Panel>

        <div className="flex flex-wrap gap-2">
          <Button variant="outline" asChild>
            <Link to="/walk-forward" search={{ variant: "baseline" }}>
              ← ผลราย fold แบบละเอียด
            </Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/walk-forward-compare">เปรียบเทียบกลไกทั้งสามแบบ</Link>
          </Button>
        </div>

        <p className="text-xs text-muted-foreground">
          Research/education เท่านั้น ไม่ใช่คำแนะนำการลงทุน · การวัด OOS ของตัวเลือกที่ถูกปฏิเสธเป็น diagnostic
          สำหรับการสอน ไม่ถูกนับใน multiple-testing count ของงานวิจัย (ไม่มีการเลือกอะไรจากมัน)
        </p>
      </div>
    </EducationShell>
  );
}
