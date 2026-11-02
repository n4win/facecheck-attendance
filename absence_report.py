"""Live reporting source including absence; preserves existing attendance dashboards."""
import json
from pathlib import Path

from attendance_sheets import AttendanceSheets
from report_setup import REPORT_HEADERS, data_formula, normalize, prepare_tab, validate_terms

BASE = Path(__file__).resolve().parent


def publish():
    terms = validate_terms(json.loads((BASE / "reports/academic_terms.json").read_text()))
    source = AttendanceSheets().connect()
    raw = source.get_all_values()
    expected, excluded = normalize(raw, terms, include_absence=True)
    book = source.spreadsheet
    tab = prepare_tab(book, "Report_Attendance_All", REPORT_HEADERS,
                      data_formula(source.title, terms, include_absence=True),
                      max(10000, source.row_count * 2))
    tab.format("A2:A", {"numberFormat": {"type": "DATE", "pattern": "yyyy-mm-dd"}})
    tab.format("C2:C", {"numberFormat": {"type": "TEXT"}})
    actual = [row for row in tab.get_all_values()[1:] if row and row[0]]
    if len(actual) != len(expected):
        raise RuntimeError(f"Report row count mismatch: {len(actual)} != {len(expected)}")
    for actual_row, expected_row in zip(actual, expected):
        for col in (0, 1, 2, 3, 4, 5, 7, 8, 9, 10, 11, 12, 13):
            if str(actual_row[col]) != str(expected_row[col]):
                raise RuntimeError(f"Report mismatch at {expected_row[10]}, {REPORT_HEADERS[col]}")
    if source.get_all_values() != raw:
        raise RuntimeError("Attendance changed during verification; rerun")
    info = {"spreadsheet_id": book.id, "worksheet_id": tab.id,
            "source_name": tab.title, "verified_rows": len(actual),
            "present": sum(row[9] for row in expected),
            "absent": sum(row[4] == "ขาดเรียน" for row in expected), "excluded": excluded}
    (BASE / "reports/absence_report_config.json").write_text(
        json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    publish()
