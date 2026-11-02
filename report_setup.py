"""Prepare live reporting views in the configured attendance spreadsheet.

Run: env/bin/python report_setup.py --publish
Does not modify the attendance worksheet or spreadsheet sharing permissions.
"""
import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path
from urllib.parse import urlencode

from attendance_sheets import AttendanceSheets, valid_headers

BASE = Path(__file__).resolve().parent
REPORT_HEADERS = ["ATTENDANCE_DATE", "YEAR_MONTH", "STUDENT_ID", "STUDENT_NAME", "STATUS",
                  "CHECKIN_TIME", "CHECKIN_MINUTES", "ON_TIME_COUNT", "LATE_COUNT",
                  "CHECKIN_COUNT", "ATTENDANCE_KEY", "ANNOTATION", "SEMESTER", "STATUS_LABEL"]
MONTH_HEADERS = ["YEAR_MONTH", "CHECKINS", "STUDENTS", "ON_TIME", "LATE", "LATE_RATE", "DAYS_WITH_RECORDS"]
STATUS_MAP = {"ตรงเวลา": "ตรงเวลา", "มา": "ตรงเวลา", "On time": "ตรงเวลา", "มาสาย": "มาสาย", "Late": "มาสาย"}
UNASSIGNED = "ยังไม่กำหนดภาคการศึกษา"


def validate_terms(terms):
    """Inclusive ISO date intervals, unique names and no overlapping semesters."""
    names, intervals = set(), []
    for term in terms:
        name = term["name"]
        if not isinstance(name, str) or not name.strip() or name != name.strip() or name in names or name == UNASSIGNED:
            raise ValueError("ชื่อภาคการศึกษาต้องไม่ว่างหรือซ้ำ")
        start, end = term["start"], term["end"]
        for value in (start, end):
            if datetime.strptime(value, "%Y-%m-%d").strftime("%Y-%m-%d") != value:
                raise ValueError("วันที่ภาคการศึกษาต้องเป็น ค.ศ. YYYY-MM-DD")
        if start > end:
            raise ValueError("วันสิ้นสุดภาคต้องไม่ก่อนวันเริ่ม")
        names.add(name)
        intervals.append((start, end))
    intervals.sort()
    if any(left[1] >= right[0] for left, right in zip(intervals, intervals[1:])):
        raise ValueError("ช่วงวันที่ภาคการศึกษาซ้อนกัน")
    return terms


def semester_for(day, terms):
    return next((t["name"] for t in terms if t["start"] <= day <= t["end"]), UNASSIGNED)


def semester_expression(terms):
    expression = f'IF(INDEX(dedup,,3)>0,"{UNASSIGNED}","")'
    for term in reversed(validate_terms(terms)):
        start = "DATE(" + term["start"].replace("-", ",") + ")"
        end = "DATE(" + term["end"].replace("-", ",") + ")"
        name = term["name"].replace('"', '""')
        expression = f'IF((INDEX(dedup,,3)>={start})*(INDEX(dedup,,3)<={end}),"{name}",{expression})'
    return expression


def normalize(rows, terms=None, include_absence=False):
    """Independent reference calculation for validating the live sheet view."""
    terms = validate_terms(terms or [])
    if rows and not valid_headers(rows[0]):
        raise ValueError("หัวคอลัมน์ข้อมูลเช็คชื่อไม่ตรงกับที่คาดไว้")
    result, excluded = {}, Counter()
    status_map = {**STATUS_MAP, **({"ขาดเรียน": "ขาดเรียน"} if include_absence else {})}
    for raw in rows[1:]:
        d, name, student_id, clock, status, note = (list(raw) + [""] * 6)[:6]
        name, student_id, status = name.strip(), str(student_id).strip(), status.strip()
        if not name or name.casefold() == "unknown" or not student_id:
            excluded["unknown_or_missing_identity"] += 1
            continue
        if status not in status_map:
            excluded["unsupported_status"] += 1
            continue
        try:
            day = datetime.strptime(d, "%d-%m-%Y").date()
            if day.strftime("%d-%m-%Y") != d:
                raise ValueError()
        except ValueError:
            excluded["invalid_date"] += 1
            continue
        try:
            parsed = datetime.strptime(clock, "%H:%M:%S")
            minutes = parsed.hour*60 + parsed.minute + parsed.second/60
        except ValueError:
            minutes = ""
        key = f"{day.isoformat()}|{student_id}"
        if key in result:
            excluded["duplicate_replaced"] += 1
        normalized = status_map[status]
        result[key] = [day.isoformat(), day.strftime("%Y-%m"), student_id, name, normalized,
                       clock, minutes, int(normalized == "ตรงเวลา"), int(normalized == "มาสาย"),
                       int(normalized != "ขาดเรียน"), key, note or "ไม่มีหมายเหตุ", semester_for(day.isoformat(), terms),
                       {"ตรงเวลา": "มาเรียน", "มาสาย": "สาย", "ขาดเรียน": "ขาดเรียน"}[normalized]]
    return [result[key] for key in sorted(result)], dict(excluded)


def data_formula(title, terms=None, include_absence=False):
    source = "'" + title.replace("'", "''") + "'"
    fallback = 'IF(originalstatus="ขาดเรียน","ขาดเรียน","")' if include_absence else '""'
    label = 'IF(INDEX(dedup,,7)="ตรงเวลา","มาเรียน",IF(INDEX(dedup,,7)="มาสาย","สาย","ขาดเรียน"))'
    return f'''=IFNA(ARRAYFORMULA(LET(
raw,FILTER(HSTACK(ROW({source}!A2:A),{source}!A2:F),{source}!A2:A<>""),
rownum,INDEX(raw,,1),datetext,TO_TEXT(INDEX(raw,,2)),
names,TRIM(INDEX(raw,,3)),ids,TRIM(TO_TEXT(INDEX(raw,,4))),
clock,TO_TEXT(INDEX(raw,,5)),originalstatus,TRIM(INDEX(raw,,6)),notes,INDEX(raw,,7),
dates,IFERROR(DATE(VALUE(RIGHT(datetext,4)),VALUE(MID(datetext,4,2)),VALUE(LEFT(datetext,2))),0),
statuses,IF(((originalstatus="ตรงเวลา")+(originalstatus="มา")+(originalstatus="On time"))>0,"ตรงเวลา",IF(((originalstatus="มาสาย")+(originalstatus="Late"))>0,"มาสาย",{fallback})),
keys,TEXT(dates,"yyyy-mm-dd")&"|"&ids,
minutes,IFERROR(IF(REGEXMATCH(clock,"^([01][0-9]|2[0-3]):[0-5][0-9]:[0-5][0-9]$"),TIMEVALUE(clock)*1440,""),""),
eligible,FILTER(HSTACK(keys,rownum,dates,TEXT(dates,"yyyy-mm"),ids,names,statuses,clock,minutes,IF(statuses="ตรงเวลา",1,0),IF(statuses="มาสาย",1,0),IF((statuses<>"")*(statuses<>"ขาดเรียน"),1,0),IF(notes="","ไม่มีหมายเหตุ",notes)),
(names<>"")*(LOWER(names)<>"unknown")*(ids<>"")*(statuses<>"")*(TEXT(dates,"dd-mm-yyyy")=datetext)),
dedup,SORTN(SORT(eligible,2,FALSE),9^9,2,1,TRUE),
HSTACK(CHOOSECOLS(dedup,3,4,5,6,7,8,9,10,11,12,1,13),{semester_expression(terms or [])},{label}))),"")'''.replace("\n", "")


def monthly_formula():
    return summary_formula("B")


def summary_formula(column):
    if column not in ("A", "B", "M"):
        raise ValueError("Unsupported reporting period")
    return '''=IFNA(LET(months,SORT(UNIQUE(FILTER(Report_Data!B2:B,Report_Data!B2:B<>""))),
checks,MAP(months,LAMBDA(m,SUMIF(Report_Data!B2:B,m,Report_Data!J2:J))),
students,MAP(months,LAMBDA(m,COUNTUNIQUE(FILTER(Report_Data!C2:C,Report_Data!B2:B=m)))),
ontime,MAP(months,LAMBDA(m,SUMIF(Report_Data!B2:B,m,Report_Data!H2:H))),
late,MAP(months,LAMBDA(m,SUMIF(Report_Data!B2:B,m,Report_Data!I2:I))),
days,MAP(months,LAMBDA(m,COUNTUNIQUE(FILTER(Report_Data!A2:A,Report_Data!B2:B=m)))),
HSTACK(months,checks,students,ontime,late,ARRAYFORMULA(IFERROR(late/checks,0)),days)),"")'''.replace("\n", "").replace("Report_Data!B2:B", f"Report_Data!{column}2:{column}")


def summarize(rows, column):
    groups = {}
    for row in rows:
        groups.setdefault(row[column], []).append(row)
    return [[period, sum(r[9] for r in items), len({r[2] for r in items}), sum(r[7] for r in items),
             sum(r[8] for r in items), sum(r[8] for r in items)/sum(r[9] for r in items) if sum(r[9] for r in items) else 0, len({r[0] for r in items})]
            for period, items in sorted(groups.items())]


def report_url(spreadsheet_id, worksheet_id):
    return "https://lookerstudio.google.com/reporting/create?" + urlencode({
        "c.mode": "edit", "r.reportName": "รายงานการเข้าเรียนรายวัน รายเดือน และรายภาคการศึกษา",
        "ds.connector": "googleSheets", "ds.spreadsheetId": spreadsheet_id,
        "ds.worksheetId": worksheet_id, "ds.hasHeader": "true", "ds.range": "A:N",
        "ds.datasourceName": "Attendance Report Data",
    })


def prepare_tab(book, title, headers, formula, rows):
    import gspread
    try:
        tab = book.worksheet(title)
        old_headers = tab.row_values(1)
        upgrade = title == "Report_Data" and old_headers == REPORT_HEADERS[:12]
        if old_headers != headers and not upgrade:
            raise ValueError(f"มีแท็บ {title} ที่ไม่ใช่โครงสร้างรายงานนี้อยู่แล้ว จึงไม่แก้ไขทับ")
        formulas = tab.get("A2", value_render_option="FORMULA")
        if formulas and formulas[0] and not str(formulas[0][0]).startswith("=IFNA("):
            raise ValueError(f"แท็บ {title} มีข้อมูลอื่นอยู่ใน A2 จึงไม่แก้ไขทับ")
        if tab.row_count < rows:
            tab.resize(rows=rows)
        if tab.col_count < len(headers):
            tab.resize(cols=len(headers))
    except gspread.WorksheetNotFound:
        tab = book.add_worksheet(title=title, rows=rows, cols=len(headers))
    tab.update(range_name="A1", values=[headers], value_input_option="RAW")
    tab.update(range_name="A2", values=[[formula]], value_input_option="USER_ENTERED")
    tab.freeze(rows=1)
    tab.format(f"A1:{chr(64+len(headers))}1", {"backgroundColor": {"red": .03, "green": .49, "blue": .51},
               "textFormat": {"bold": True, "foregroundColor": {"red": 1, "green": 1, "blue": 1}}})
    return tab


def publish():
    config_path = BASE / "reports" / "looker_studio_config.json"
    previous = json.loads(config_path.read_text(encoding="utf-8")) if config_path.exists() else {}
    terms_path = BASE / "reports" / "academic_terms.json"
    terms = validate_terms(json.loads(terms_path.read_text(encoding="utf-8")))
    source = AttendanceSheets().connect()
    raw = source.get_all_values()
    expected, excluded = normalize(raw, terms, include_absence=True)
    book = source.spreadsheet
    tab = prepare_tab(book, "Report_Data", REPORT_HEADERS, data_formula(source.title, terms, include_absence=True), max(10000, source.row_count*2))
    tab.format("A2:A", {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}})
    tab.format("C2:C", {"numberFormat": {"type": "TEXT"}})
    monthly = prepare_tab(book, "Report_Monthly", MONTH_HEADERS, monthly_formula(), 1000)
    monthly.format("F2:F", {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}})
    daily = prepare_tab(book, "Report_Daily", ["ATTENDANCE_DATE"] + MONTH_HEADERS[1:], summary_formula("A"), max(1000, source.row_count))
    daily.format("A2:A", {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}})
    daily.format("F2:F", {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}})
    semester = prepare_tab(book, "Report_Semester", ["SEMESTER"] + MONTH_HEADERS[1:], summary_formula("M"), 1000)
    semester.format("F2:F", {"numberFormat": {"type": "PERCENT", "pattern": "0.0%"}})
    actual = tab.get_all_values()[1:]
    actual = [row for row in actual if row and row[0]]
    errors = [row for row in actual if any(str(cell).startswith(("#ERROR", "#REF", "#VALUE", "#NAME", "#N/A")) for cell in row)]
    if errors or len(actual) != len(expected):
        raise RuntimeError(f"ตรวจผลสูตรไม่ผ่าน: คาด {len(expected)} แถว ได้ {len(actual)} แถว; formula_errors={bool(errors)}")
    for actual_row, expected_row in zip(actual, expected):
        for col in (0, 1, 2, 3, 4, 7, 8, 9, 10, 11, 12, 13):
            if str(actual_row[col]) != str(expected_row[col]):
                raise RuntimeError(f"ข้อมูลผลสูตรไม่ตรงกับการตรวจอิสระที่คอลัมน์ {REPORT_HEADERS[col]}")
    for summary_tab, column in ((daily, 0), (monthly, 1), (semester, 12)):
        values = [row for row in summary_tab.get_all_values()[1:] if row and row[0]]
        numeric = [row for row in summary_tab.get_all_values(value_render_option="UNFORMATTED_VALUE")[1:] if row and row[0]]
        reference = summarize(expected, column)
        if len(values) != len(reference) or len(numeric) != len(reference):
            raise RuntimeError(f"จำนวนกลุ่มสรุปไม่ตรง: {summary_tab.title}")
        for display, numbers, wanted in zip(values, numeric, reference):
            if display[0] != wanted[0] or any(abs(float(numbers[i])-wanted[i]) > 1e-8 for i in range(1, 7)):
                raise RuntimeError(f"ยอดสรุปไม่ตรง: {summary_tab.title}")
    if source.get_all_values() != raw:
        raise RuntimeError("ข้อมูลต้นทางเปลี่ยนระหว่างตรวจ กรุณารันใหม่เพื่อตรวจยอดล่าสุด")
    info = {"spreadsheet_id": book.id, "source_worksheet_id": source.id,
            "report_worksheet_id": tab.id, "monthly_worksheet_id": monthly.id,
            "daily_worksheet_id": daily.id, "semester_worksheet_id": semester.id,
            "academic_terms": terms,
            "unassigned_semester_records": sum(row[12] == UNASSIGNED for row in expected),
            "sheet_url": f"https://docs.google.com/spreadsheets/d/{book.id}/edit#gid={tab.id}",
            "create_report_url": report_url(book.id, tab.id),
            "verified_at": datetime.now().astimezone().isoformat(),
            "valid_records": len(expected), "excluded": excluded,
            "months": sorted({row[1] for row in expected}),
            "monthly_summary": monthly.get_all_values(),
            "report_status": "data_ready_report_layout_requires_looker_studio_editor"}
    folder = BASE / "reports"
    folder.mkdir(exist_ok=True)
    # Preserve dashboard layout metadata maintained through the report editor.
    info = {**previous, **info}
    config_path.write_text(json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--publish", action="store_true", help="Prepare report tabs in the configured attendance spreadsheet")
    if parser.parse_args().publish:
        publish()
    else:
        parser.print_help()
