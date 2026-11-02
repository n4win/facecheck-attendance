"""Attendance destination: the user's Google Sheet, or a local CSV; no network on import."""
import csv
from datetime import date
import os
from pathlib import Path
import re

from app_paths import DATA_DIR
import google_settings

HEADERS = ["DATE", "NAME", "STUDENT_ID", "TIME", "STATUS", "ANNOTATION"]
LOCAL_RECORDS = DATA_DIR / "attendance_records.csv"


def valid_headers(values):
    return [value.strip().upper() for value in values[:6]] == HEADERS


class LocalWorksheet:
    """ไฟล์ CSV ที่มีเมธอดเท่าที่โปรแกรมใช้จาก Google worksheet ใช้เมื่อไม่ได้เชื่อม Google."""

    def __init__(self, path):
        self.path = Path(path)

    @property
    def spreadsheet(self):
        raise ValueError("คำสั่งนี้ต้องเชื่อม Google Sheets ก่อน")

    def get_all_values(self):
        if not self.path.exists():
            return []
        # utf-8-sig ทำให้ Excel แสดงภาษาไทยถูกต้อง
        with self.path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.reader(handle))

    def write(self, rows):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(f"{self.path.name}.{os.getpid()}.tmp")
        with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
            csv.writer(handle).writerows(rows)
        temporary.replace(self.path)

    def update(self, range_name, values, value_input_option=None):
        row = int(re.fullmatch(r"A(\d+):F\1", range_name).group(1))
        rows = self.get_all_values()
        rows.extend([] for _ in range(row - len(rows)))
        rows[row - 1] = values[0]
        self.write(rows)

    def append_row(self, values, value_input_option=None):
        self.write(self.get_all_values() + [values])

    def delete_rows(self, index):
        rows = self.get_all_values()
        del rows[index - 1]
        self.write(rows)


def open_google_worksheet(spreadsheet, key_path):
    import gspread
    from oauth2client.service_account import ServiceAccountCredentials

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    client = gspread.authorize(ServiceAccountCredentials.from_json_keyfile_name(str(key_path), scope))
    client.set_timeout((10, 30))
    book = client.open_by_url(spreadsheet) if spreadsheet.startswith("https://") else client.open(spreadsheet)
    return book.sheet1


def check_google_sheet(spreadsheet, key_path):
    """ทดสอบแบบอ่านอย่างเดียว คืนค่าว่าชีตนี้ติดตั้งระบบสรุปขาดเรียนแล้วหรือไม่."""
    from attendance_sessions import SESSION_SHEET

    sheet = open_google_worksheet(spreadsheet, key_path)
    headers = sheet.row_values(1)
    if headers and not valid_headers(headers):
        raise ValueError("แถวแรกของแผ่นแรกต้องเป็น " + ", ".join(HEADERS) + " หรือเป็นชีตว่าง")
    return SESSION_SHEET in [tab.title for tab in sheet.spreadsheet.worksheets()]


class AttendanceSheets:
    def __init__(self, worksheet=None):
        self.worksheet = worksheet

    def connect(self):
        if self.worksheet is None:
            settings = google_settings.load()
            if settings is None:
                self.worksheet = LocalWorksheet(LOCAL_RECORDS)
            else:
                self.worksheet = open_google_worksheet(settings["spreadsheet"], google_settings.KEY_PATH)
        return self.worksheet

    def open_session(self, session_id, day, students, end_time=None):
        sheet = self.connect()
        settings = google_settings.load()
        # รอบเช็คชื่อมีไว้ให้ Apps Script สรุปขาดเรียน ถ้าไม่ได้ติดตั้งก็ไม่ต้องส่ง
        if isinstance(sheet, LocalWorksheet) or (settings is not None and not settings.get("auto_absence", True)):
            return 0
        from attendance_sessions import publish_session
        return publish_session(sheet, session_id, day, students, end_time=end_time)

    def send(self, item):
        sheet = self.connect()
        values = sheet.get_all_values()
        if not values:
            sheet.update(range_name="A1:F1", values=[HEADERS], value_input_option="RAW")
        elif not valid_headers(values[0]):
            raise ValueError("คอลัมน์ในชีตไม่ตรงกับ DATE, NAME, STUDENT_ID, TIME, STATUS, ANNOTATION")
        day = date.fromisoformat(item["day"]).strftime("%d-%m-%Y")
        matches = [(index, row) for index, row in enumerate(values[1:], 2)
                   if len(row) >= 3 and row[0].strip() == day
                   and row[2].strip() == item["student_id"]]
        if len(matches) > 1:
            raise ValueError(f"พบรหัส {item['student_id']} วันที่ {day} ซ้ำในชีต กรุณาตรวจสอบก่อนส่งใหม่")
        if item["status"] is None:
            if matches:
                sheet.delete_rows(matches[0][0])
            return
        annotation = matches[0][1][5] if matches and len(matches[0][1]) > 5 else "ไม่มีหมายเหตุ"
        row = [day, item["name"], item["student_id"], item["updated_at"],
               {"มา": "ตรงเวลา", "มาสาย": "มาสาย"}[item["status"]], annotation]
        if matches:
            sheet.update(range_name=f"A{matches[0][0]}:F{matches[0][0]}", values=[row], value_input_option="RAW")
        else:
            sheet.append_row(row, value_input_option="RAW")
