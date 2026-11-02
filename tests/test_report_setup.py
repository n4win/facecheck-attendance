import unittest
from urllib.parse import urlparse, parse_qs
from attendance_sheets import HEADERS
from report_setup import normalize, data_formula, report_url, validate_terms, summarize, UNASSIGNED


class ReportTests(unittest.TestCase):
    def test_semester_inclusive_boundaries_cross_year_and_unassigned(self):
        terms = [{"name": "2/2569", "start": "2026-11-01", "end": "2027-03-31"}]
        rows, _ = normalize([HEADERS] + [[d, "A", "001", "08:00:00", "ตรงเวลา", ""]
                                       for d in ["31-10-2026", "01-11-2026", "31-03-2027", "01-04-2027"]], terms)
        self.assertEqual([r[12] for r in rows], [UNASSIGNED, "2/2569", "2/2569", UNASSIGNED])
        self.assertEqual(rows[0][13], "มาเรียน")

    def test_invalid_semesters_rejected(self):
        for terms in [
            [{"name": "1", "start": "2026-10-01", "end": "2026-09-01"}],
            [{"name": "1", "start": "2026-02-30", "end": "2026-09-01"}],
            [{"name": "1", "start": "2026-01-01", "end": "2026-06-01"},
             {"name": "2", "start": "2026-06-01", "end": "2026-12-01"}],
            [{"name": "1", "start": "2026-01-01", "end": "2026-02-01"},
             {"name": "1", "start": "2026-03-01", "end": "2026-04-01"}],
        ]:
            with self.subTest(terms=terms), self.assertRaises(ValueError):
                validate_terms(terms)

    def test_period_counts_unique_students_and_weighted_rates(self):
        rows, _ = normalize([HEADERS,
            ["01-09-2026", "A", "001", "08:00:00", "ตรงเวลา", ""],
            ["02-09-2026", "A", "001", "09:00:00", "มาสาย", ""],
            ["02-09-2026", "B", "002", "09:00:00", "มาสาย", ""]])
        self.assertEqual(summarize(rows, 1), [["2026-09", 3, 2, 1, 2, 2/3, 2]])
        self.assertEqual(len(summarize(rows, 0)), 2)
        self.assertEqual(summarize(rows, 12)[0][0], UNASSIGNED)
        self.assertEqual(summarize([], 0), [])
        self.assertEqual(rows[-1][13], "สาย")

    def test_dates_months_statuses_and_leading_zero_id(self):
        rows, _ = normalize([HEADERS, ["01-09-2026", "นักศึกษา", "001", "08:30:00", "On time", ""],
                                     ["01-10-2026", "นักศึกษา", "001", "09:00:00", "Late", "รถติด"]])
        self.assertEqual([row[1] for row in rows], ["2026-09", "2026-10"])
        self.assertEqual(rows[0][2], "001")
        self.assertEqual(rows[0][6:10], [510, 1, 0, 1])
        self.assertEqual(rows[1][7:10], [0, 1, 1])

    def test_latest_duplicate_wins_not_counted_twice(self):
        rows, excluded = normalize([HEADERS, ["01-09-2026", "A", "001", "08:00:00", "ตรงเวลา", ""],
                                     ["01-09-2026", "A", "001", "09:00:00", "มาสาย", "รถติด"]])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][4], "มาสาย")
        self.assertEqual(excluded["duplicate_replaced"], 1)

    def test_excludes_unknown_invalid_dates_missing_id_and_absence(self):
        rows, excluded = normalize([HEADERS, ["01-09-2026", " Unknown ", "001", "", "ตรงเวลา", ""],
                                     ["31-02-2026", "A", "001", "", "ตรงเวลา", ""],
                                     ["01-09-2026", "A", "", "", "ตรงเวลา", ""],
                                     ["01-09-2026", "A", "001", "", "ขาดเรียน", ""]])
        self.assertEqual(rows, [])
        self.assertEqual(sum(excluded.values()), 4)

    def test_sheet_name_escaped_and_report_link_targets_tab(self):
        self.assertIn("'Teacher''s Data'!A2:A", data_formula("Teacher's Data"))
        params = parse_qs(urlparse(report_url("test-id", 123)).query)
        self.assertEqual(params["ds.worksheetId"], ["123"])
        self.assertEqual(params["ds.connector"], ["googleSheets"])


if __name__ == "__main__":
    unittest.main()
