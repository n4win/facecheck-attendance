"""One-time historical absence backfill using the current registered roster.

Preview by default; --apply writes missing rows to the existing attendance sheet.
Only past dates with real attendance qualify. No attendance sessions are fabricated.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
import sqlite3

from app_paths import DATA_DIR
from attendance_sessions import THAILAND, session_rows
from attendance_sheets import AttendanceSheets, valid_headers

PRESENT = {"ตรงเวลา", "มาตรงเวลา", "มา", "มาเรียน", "มาสาย", "สาย"}


def plan_backfill(values, students, today):
    if not values or not valid_headers(values[0]):
        raise ValueError("หัวคอลัมน์ชีตเช็คชื่อไม่ถูกต้อง")
    roster = session_rows("backfill-preview", today.strftime("%d-%m-%Y"), students)
    days, existing = set(), set()
    for number, row in enumerate(values[1:], 2):
        if not any(str(v).strip() for v in row):
            continue
        if len(row) < 5:
            raise ValueError(f"ข้อมูลแถว {number} ไม่ครบ")
        day, name, sid, _, status = [str(v).strip() for v in row[:5]]
        try:
            parsed = datetime.strptime(day, "%d-%m-%Y").date()
        except ValueError:
            raise ValueError(f"วันที่แถว {number} ไม่ถูกต้อง: {day}") from None
        if parsed.strftime("%d-%m-%Y") != day:
            raise ValueError(f"รูปแบบวันที่แถว {number} ไม่ถูกต้อง")
        if sid:
            existing.add((day, sid))  # Preserve every existing status.
        if parsed < today and sid and name and name.casefold() != "unknown" and status in PRESENT:
            days.add(parsed)
    return [[day.strftime("%d-%m-%Y"), r[3], r[2], "-", "ขาดเรียน", "ไม่มีหมายเหตุ"]
            for day in sorted(days) for r in roster
            if (day.strftime("%d-%m-%Y"), r[2]) not in existing]


def check_pending():
    outbox = DATA_DIR / "face_attendance_pending.json"
    if outbox.exists() and json.loads(outbox.read_text(encoding="utf-8")):
        raise ValueError("มีรายการสแกนค้างส่ง กรุณาซิงก์ก่อนเติมขาดย้อนหลัง")
    database = DATA_DIR / "manual_attendance.sqlite3"
    if database.exists():
        with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as db:
            if db.execute("SELECT COUNT(*) FROM sheets_queue").fetchone()[0]:
                raise ValueError("มีรายการเช็คมือค้างส่ง กรุณาซิงก์ก่อนเติมขาดย้อนหลัง")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="Use current roster and append missing historical absences")
    args = parser.parse_args()
    from studata import StudentStore
    students = [{"name": r["name"], "student_id": str(r["stu_id"])} for r in StudentStore().rows()]
    check_pending()
    sheet = AttendanceSheets().connect()
    book = sheet.spreadsheet
    if sheet.id != 0:
        raise ValueError("ชีตปลายทางต้องเป็นแผ่นแรกของไฟล์เช็คชื่อ")
    today = datetime.now(THAILAND).date()
    before = sheet.get_all_values()
    planned = plan_backfill(before, students, today)
    print(json.dumps({"spreadsheet": book.title, "roster_count": len(students), "add_count": len(planned),
                      "by_date": dict(Counter(r[0] for r in planned))}, ensure_ascii=False), flush=True)
    if not args.apply or not planned:
        return
    check_pending()
    # Re-read just before append, refusing a changed source rather than overwriting.
    if sheet.get_all_values() != before:
        raise ValueError("ชีตเปลี่ยนระหว่างตรวจ กรุณารันใหม่")
    audit_dir = DATA_DIR / "backfill_audit"
    audit_dir.mkdir(exist_ok=True)
    audit = audit_dir / (datetime.now(THAILAND).strftime("%Y%m%d_%H%M%S_%f") + ".json")
    payload = {"basis": "current registered roster; past dates with existing attendance",
               "before": before, "planned": planned, "verified": False}
    audit.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    sheet.append_rows(planned, value_input_option="RAW")
    after = sheet.get_all_values()
    if after[:len(before)] != before or any(after.count(r) != 1 for r in planned):
        raise RuntimeError("การตรวจหลังบันทึกพบข้อมูลเปลี่ยน กรุณาตรวจชีตและไฟล์ audit")
    if plan_backfill(after, students, today):
        raise RuntimeError("ยังมีรายการขาดที่เติมไม่ครบ กรุณาตรวจชีต")
    payload["verified"] = True
    audit.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Verified: {len(planned)} rows added; existing rows preserved; no duplicate additions.")
    print(f"Audit: {audit}")


if __name__ == "__main__":
    main()
