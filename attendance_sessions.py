"""Publish attendance-round rosters for the Google-hosted absence scheduler.

Only names and student IDs are sent; face images/embeddings stay on the computer.
"""
from datetime import datetime
from zoneinfo import ZoneInfo

SESSION_SHEET = "Attendance_Sessions"
SESSION_HEADERS = ["SESSION_ID", "DATE", "STUDENT_ID", "NAME", "OPENED_AT", "ROSTER_COUNT", "END_TIME"]
THAILAND = ZoneInfo("Asia/Bangkok")


def session_rows(session_id, day, students, opened_at=None, end_time=None):
    """Snapshot a complete round. Dates in DATE match the existing attendance sheet."""
    parsed = datetime.strptime(day, "%d-%m-%Y")
    if parsed.strftime("%d-%m-%Y") != day:
        raise ValueError("วันที่เปิดรอบไม่ถูกต้อง")
    if not session_id:
        raise ValueError("ไม่พบรหัสรอบเช็คชื่อ")
    if end_time is not None:
        parsed_time = datetime.strptime(end_time, "%H:%M")
        if parsed_time.strftime("%H:%M") != end_time:
            raise ValueError("เวลาเลิกเรียนต้องเป็น HH:MM")
    roster = {}
    for student in students:
        name = str(student["name"]).strip()
        student_id = str(student["student_id"]).strip()
        if name.casefold() == "unknown":
            continue
        if not name or not student_id or student_id in roster:
            raise ValueError("ชื่อหรือรหัสนักศึกษาว่าง/ซ้ำ กรุณาตรวจสอบข้อมูลนักศึกษา")
        roster[student_id] = name
    if not roster:
        raise ValueError("ไม่มีรายชื่อนักศึกษาสำหรับเปิดรอบเช็คชื่อ")
    opened = opened_at or datetime.now(THAILAND)
    if opened.tzinfo is None:
        raise ValueError("เวลาเปิดรอบต้องระบุเขตเวลา")
    stamp = opened.astimezone(THAILAND).isoformat(timespec="seconds")
    return [[session_id, day, sid, name, stamp, len(roster)] + ([end_time] if end_time is not None else []) for sid, name in roster.items()]


def publish_session(attendance_sheet, session_id, day, students, end_time=None):
    """One RAW append publishes the entire snapshot; retries reuse the same ID."""
    from gspread.exceptions import WorksheetNotFound

    rows = session_rows(session_id, day, students, end_time=end_time)
    try:
        sheet = attendance_sheet.spreadsheet.worksheet(SESSION_SHEET)
    except WorksheetNotFound:
        raise ValueError("ยังไม่ได้ติดตั้งระบบสรุปขาดเรียนบน Google กรุณาติดตั้งตาม docs/AUTO_ABSENCE.md") from None
    values = sheet.get_all_values()
    if not values or values[0][:6] != SESSION_HEADERS[:6]:
        raise ValueError("หัวคอลัมน์ Attendance_Sessions ไม่ถูกต้อง")
    if end_time is not None and values[0][6:7] != ["END_TIME"]:
        raise ValueError("กรุณาอัปเดต AutoAbsence.gs บน Google และรัน setupAttendanceAutomation ก่อนใช้เวลาเลิกเรียน")
    existing = [row for row in values[1:] if row and row[0] == session_id]
    if existing:
        expected = {(r[1], r[2], r[3], str(r[5]), r[6] if len(r) > 6 else "") for r in rows}
        actual = {(r[1], r[2], r[3], r[5], r[6] if len(r) > 6 else "") for r in existing if len(r) >= 6}
        if len(existing) != len(rows) or actual != expected:
            raise ValueError("ข้อมูลรอบเช็คชื่อไม่ครบหรือเปลี่ยนแปลง กรุณาตรวจสอบ Attendance_Sessions")
        return len(rows)
    sheet.append_rows(rows, value_input_option="RAW")
    return len(rows)
