---
name: reflect
description: Record a correction the user made during this session as a durable lesson in docs/AGENT_LESSONS.md. Use when the user corrects an approach, says something was wrong or "ยังไม่โอเค", or establishes a standing rule ("never/always", "ห้าม/ต้อง"), and the lesson would otherwise be lost at session end. Do NOT use for praise or acknowledgement.
---

# Reflect — บันทึกบทเรียนจากการถูกแก้

อ่าน `docs/AGENT_LESSONS.md` ตอนเริ่ม session ที่เกี่ยวกับงานเดิม และเรียก skill นี้
เมื่อผู้ใช้ **แก้** สิ่งที่ทำไป

## ห้ามบันทึกอะไร

- **คำชม / การตอบรับ** — "ได้", "โอเค", "perfect", "works great"
  การตอบรับไม่เท่ากับการรับรองว่าถูก ใน session ที่ทำให้เกิด module นี้ ผู้ใช้ตอบ "ได้"
  กับเกือบทุกข้อเสนอ รวมข้อเสนอที่ผิด (บอกให้เอาลิงก์ไปให้นักเรียนทั้งที่เว็บยัง 404)
  ถ้าเก็บคำตอบรับเป็นสัญญาณ จะกลายเป็นบันทึกความผิดพลาดว่าเป็นแนวทางที่ถูกต้อง
- **ความเห็นของตัวเองที่ยังไม่มีหลักฐาน** — ต้องมีเหตุการณ์จริงรองรับ

## ห้ามเขียนไฟล์ไหน

`CLAUDE.md`, `AGENTS.md`, `ROUTING.md`, `docs/AOT_VALIDATION_CRITERIA.md`,
`docs/VALIDATION_LOG.md`, `gate/**`, `experiments/**`

กฎ เกณฑ์ที่ประกาศแล้ว และ gate **ไม่ใช่สิ่งที่เรียนรู้เองได้** — การแก้ไฟล์เหล่านี้เป็น
การตัดสินใจของมนุษย์เท่านั้น `agent/reflect.py` บังคับข้อนี้ในโค้ด และมีเทสต์คุมไว้

## ขั้นตอน

1. ระบุ **การแก้** ที่เกิดขึ้นจริงใน session (ไม่ใช่การตอบรับ)
2. เขียนเป็น 3 ส่วน: `trigger` (สถานการณ์ที่ใช้กฎนี้) · `rule` (ทำอะไร) ·
   `evidence` (เกิดอะไรขึ้นจริงถึงได้กฎนี้มา)
3. **เสนอให้ผู้ใช้ดูก่อนเขียน** — ไม่มีโหมดอัตโนมัติ ไม่มีอะไรรับรองตัวเอง
4. เมื่อผู้ใช้อนุมัติ เรียก:

```bash
python -c "from datetime import date; from pathlib import Path; from agent.reflect import Lesson, append_lesson; print(append_lesson(Path('.'), Lesson(trigger='...', rule='...', evidence='...', recorded_on=date.today())))"
```

`append_lesson` จะปฏิเสธเองถ้า: เป็นคำชม · หลักฐานบางเกินไป · ปลายทางเป็นไฟล์ต้องห้าม ·
บทเรียนซ้ำกับที่มีอยู่แล้ว

## ตรวจ

```bash
python -m unittest tests.test_reflect
```
