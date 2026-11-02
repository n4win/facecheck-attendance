import unittest
from attendance_sheets import HEADERS
from report_setup import normalize, data_formula, summarize


class AbsenceReportTests(unittest.TestCase):
    def test_absence_is_visible_but_not_a_checkin(self):
        values = [HEADERS,
                  ["01-10-2026", "A", "001", "09:00:00", "ตรงเวลา", ""],
                  ["01-10-2026", "B", "002", "09:30:00", "มาสาย", ""],
                  ["01-10-2026", "C", "003", "-", "ขาดเรียน", "ไม่มีหมายเหตุ"],
                  ["01-10-2026", "Unknown", "", "-", "ขาดเรียน", ""]]
        rows, _ = normalize(values, include_absence=True)
        self.assertEqual(len(rows), 3)
        self.assertEqual(sum(r[9] for r in rows), 2)
        self.assertEqual(rows[2][5:10], ["-", "", 0, 0, 0])
        self.assertEqual(rows[2][13], "ขาดเรียน")
        self.assertEqual(len(normalize(values)[0]), 2)

    def test_later_checkin_replaces_absence(self):
        values = [HEADERS, ["01-10-2026", "A", "001", "-", "ขาดเรียน", ""],
                  ["01-10-2026", "A", "001", "09:30:00", "มาสาย", ""]]
        rows, _ = normalize(values, include_absence=True)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][9], 1)

    def test_formula_opt_in(self):
        self.assertIn('IF(originalstatus="ขาดเรียน","ขาดเรียน","")', data_formula("ชีต1", include_absence=True))
        self.assertNotIn('IF(originalstatus="ขาดเรียน","ขาดเรียน","")', data_formula("ชีต1"))

    def test_absence_does_not_inflate_attendance_or_late_rate(self):
        values = [HEADERS, ["01-10-2026", "A", "001", "09:30:00", "มาสาย", ""],
                  ["01-10-2026", "B", "002", "-", "ขาดเรียน", ""],
                  ["01-11-2026", "B", "002", "-", "ขาดเรียน", ""]]
        rows, _ = normalize(values, include_absence=True)
        self.assertEqual(summarize(rows, 1), [["2026-10", 1, 2, 0, 1, 1.0, 1],
                                              ["2026-11", 0, 1, 0, 0, 0, 1]])
