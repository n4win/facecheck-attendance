import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlparse

from app_paths import ABSENCE_SCRIPT_PATH
import teacher_report

TEMPLATE = {"report_id": "report-1", "data_sources": {"ds0": "Report_Data", "ds1": "Report_Attendance_All"}}


class Tab:
    def __init__(self, title, tab_id):
        self.title, self.id = title, tab_id


class ReportTests(unittest.TestCase):
    def source(self, tabs):
        source = Mock(title="ชีต1", row_count=1000)
        source.spreadsheet.worksheets.return_value = tabs
        return source

    def test_link_replaces_every_data_source_with_the_teachers_sheet(self):
        link = teacher_report.report_link(TEMPLATE, "sheet-id", {"Report_Data": 11, "Report_Attendance_All": 22})
        self.assertTrue(link.startswith("https://datastudio.google.com/reporting/create?"))
        query = parse_qs(urlparse(link).query)
        self.assertEqual(query["c.reportId"], ["report-1"])
        self.assertEqual(query["c.mode"], ["view"])
        for alias, tab in (("ds0", "11"), ("ds1", "22")):
            self.assertEqual(query[f"ds.{alias}.connector"], ["googleSheets"])
            self.assertEqual(query[f"ds.{alias}.spreadsheetId"], ["sheet-id"])
            self.assertEqual(query[f"ds.{alias}.worksheetId"], [tab])
            self.assertEqual(query[f"ds.{alias}.refreshFields"], ["false"])

    def test_first_open_creates_tabs_and_later_opens_write_nothing(self):
        created = []

        def make(book, title, headers, formula, rows):
            created.append((title, formula))
            return Mock(id=len(created) + 100)

        source = self.source([Tab("ชีต1", 0)])
        with patch.object(teacher_report, "prepare_tab", side_effect=make):
            ids = teacher_report.prepare_tabs(source, ["Report_Data", "Report_Attendance_All"])
        self.assertEqual(ids, {"Report_Data": 101, "Report_Attendance_All": 102})
        self.assertIn("ชีต1", created[0][1])
        self.assertIn("ขาดเรียน", created[0][1])

        source = self.source([Tab("ชีต1", 0), Tab("Report_Data", 5), Tab("Report_Attendance_All", 6)])
        with patch.object(teacher_report, "prepare_tab") as prepare:
            self.assertEqual(teacher_report.prepare_tabs(source, ["Report_Data", "Report_Attendance_All"]),
                             {"Report_Data": 5, "Report_Attendance_All": 6})
        prepare.assert_not_called()

    def test_missing_template_explains_itself(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(teacher_report, "TEMPLATE_PATH", Path(folder) / "none.json"):
            with self.assertRaisesRegex(ValueError, "รายงานต้นแบบ"):
                teacher_report.load_template()

    def test_prepare_report_uses_the_signed_in_sheet(self):
        source = self.source([Tab("ชีต1", 0), Tab("Report_Data", 5), Tab("Report_Attendance_All", 6)])
        source.spreadsheet.id = "teacher-sheet"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "template.json"
            path.write_text(json.dumps(TEMPLATE), encoding="utf-8")
            with patch.object(teacher_report, "TEMPLATE_PATH", path), \
                 patch.object(teacher_report.AttendanceSheets, "connect", return_value=source):
                link = teacher_report.prepare_report()
        self.assertEqual(parse_qs(urlparse(link).query)["ds.ds0.spreadsheetId"], ["teacher-sheet"])


class AbsenceScriptTests(unittest.TestCase):
    def test_script_has_no_fixed_sheet_and_uses_only_the_current_document(self):
        code = ABSENCE_SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertIn("@OnlyCurrentDoc", code)
        self.assertIn("function setupAttendanceAutomation", code)
        self.assertNotIn("spreadsheetId", code)
        self.assertNotIn("openById", code)


if __name__ == "__main__":
    unittest.main()
