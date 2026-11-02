import unittest
from datetime import date

from attendance_sheets import HEADERS
from backfill_absences import plan_backfill


class BackfillTests(unittest.TestCase):
    def setUp(self):
        self.roster = [{"name": "A", "student_id": "001"},
                       {"name": "B", "student_id": "002"},
                       {"name": "Unknown", "student_id": ""}]
        self.today = date(2026, 9, 30)

    def test_only_past_attended_dates_and_retry_is_idempotent(self):
        values = [HEADERS, ["29-09-2026", "A", "001", "10:00", "มาสาย", ""],
                  ["30-09-2026", "A", "001", "10:00", "ตรงเวลา", ""],
                  ["01-10-2026", "A", "001", "10:00", "ตรงเวลา", ""]]
        planned = plan_backfill(values, self.roster, self.today)
        self.assertEqual(planned, [["29-09-2026", "B", "002", "-", "ขาดเรียน", "ไม่มีหมายเหตุ"]])
        self.assertEqual(plan_backfill(values + planned, self.roster, self.today), [])

    def test_all_existing_statuses_preserved(self):
        values = [HEADERS, ["29-09-2026", "A", "001", "10:00", "มา", ""],
                  ["29-09-2026", "B", "002", "-", "ลา", ""]]
        self.assertEqual(plan_backfill(values, self.roster, self.today), [])

    def test_unknown_and_absence_alone_do_not_open_dates(self):
        values = [HEADERS, ["29-09-2026", "Unknown", "999", "10:00", "ตรงเวลา", ""],
                  ["28-09-2026", "B", "002", "-", "ขาดเรียน", ""]]
        self.assertEqual(plan_backfill(values, self.roster, self.today), [])

    def test_invalid_date_and_duplicate_roster_rejected(self):
        with self.assertRaises(ValueError):
            plan_backfill([HEADERS, ["31-09-2026", "A", "001", "-", "มา"]], self.roster, self.today)
        with self.assertRaises(ValueError):
            plan_backfill([HEADERS], self.roster + [self.roster[0]], self.today)
