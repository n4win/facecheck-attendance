"""Attendance destination: the Google Sheet of the signed-in user; no network on import."""
from datetime import date

import google_settings

HEADERS = ["DATE", "NAME", "STUDENT_ID", "TIME", "STATUS", "ANNOTATION"]
SIGN_IN_REQUIRED = "กรุณาเข้าสู่ระบบ Google ก่อนเช็คชื่อ จากปุ่มตั้งค่าในเมนูหลัก"


def valid_headers(values):
    return [value.strip().upper() for value in values[:6]] == HEADERS


def spreadsheet_url(settings):
    if not settings:
        return None
    if settings.get("spreadsheet_id"):
        return f"https://docs.google.com/spreadsheets/d/{settings['spreadsheet_id']}/edit"
    link = str(settings.get("spreadsheet", ""))
    return link if link.startswith("https://") else None


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
                raise ValueError(SIGN_IN_REQUIRED)
            if "spreadsheet_id" in settings:
                import google_auth
                self.worksheet = google_auth.open_worksheet(settings["spreadsheet_id"])
            else:
                self.worksheet = open_google_worksheet(settings["spreadsheet"], google_settings.KEY_PATH)
        return self.worksheet

    def open_session(self, session_id, day, students, end_time=None):
        sheet = self.connect()
        settings = google_settings.load()
        # รอบเช็คชื่อมีไว้ให้ Apps Script สรุปขาดเรียน ถ้าไม่ได้ติดตั้งก็ไม่ต้องส่ง
        if settings is not None and not settings.get("auto_absence", True):
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
