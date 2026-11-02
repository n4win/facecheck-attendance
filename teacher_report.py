"""เตรียมแท็บรายงานในชีตของครู แล้วเปิดรายงานต้นแบบ Looker Studio ด้วยข้อมูลของครูคนนั้น."""
import json
from urllib.parse import urlencode

from app_paths import RESOURCE_DIR
from attendance_sheets import AttendanceSheets
from report_setup import REPORT_HEADERS, data_formula, prepare_tab, validate_terms

TEMPLATE_PATH = RESOURCE_DIR / "reports" / "report_template.json"
TERMS_PATH = RESOURCE_DIR / "reports" / "academic_terms.json"
REPORT_URL = "https://datastudio.google.com/reporting/create?"


def load_template():
    """รายงานต้นแบบใช้ข้อมูลปลอม จึงเก็บรหัสรายงานใน repo สาธารณะได้."""
    try:
        template = json.loads(TEMPLATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise ValueError("รุ่นนี้ยังไม่มีรายงานต้นแบบ") from None
    if not template.get("report_id") or not template.get("data_sources"):
        raise ValueError("ไฟล์รายงานต้นแบบไม่ครบ")
    return template


def prepare_tabs(source, titles):
    """สร้างเฉพาะแท็บที่ยังไม่มี โดยไม่แก้แท็บผลเช็คชื่อ คืนรหัสของแต่ละแท็บ."""
    book = source.spreadsheet
    existing = {tab.title: tab.id for tab in book.worksheets()}
    missing = [title for title in titles if title not in existing]
    if missing:
        terms = validate_terms(json.loads(TERMS_PATH.read_text(encoding="utf-8")))
        formula = data_formula(source.title, terms, include_absence=True)
        for title in missing:
            tab = prepare_tab(book, title, REPORT_HEADERS, formula, max(10000, source.row_count * 2))
            tab.format("A2:A", {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}})
            tab.format("C2:C", {"numberFormat": {"type": "TEXT"}})
            existing[title] = tab.id
    return {title: existing[title] for title in titles}


def report_link(template, spreadsheet_id, tab_ids):
    params = {"c.reportId": template["report_id"], "c.mode": "view"}
    for alias, title in template["data_sources"].items():
        params.update({f"ds.{alias}.connector": "googleSheets", f"ds.{alias}.spreadsheetId": spreadsheet_id,
                       f"ds.{alias}.worksheetId": tab_ids[title], f"ds.{alias}.hasHeader": "true",
                       # คงชนิดฟิลด์ของต้นแบบ เช่น รหัสนักศึกษาต้องเป็นข้อความ
                       f"ds.{alias}.refreshFields": "false"})
    return REPORT_URL + urlencode(params)


def prepare_report():
    template = load_template()
    source = AttendanceSheets().connect()
    titles = list(dict.fromkeys(template["data_sources"].values()))
    return report_link(template, source.spreadsheet.id, prepare_tabs(source, titles))
