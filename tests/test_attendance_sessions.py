from datetime import datetime, timezone
import unittest
from unittest.mock import Mock

from attendance_sessions import SESSION_HEADERS, publish_session, session_rows


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.students = [{"name": "นักศึกษา", "student_id": "001"},
                         {"name": "Unknown", "student_id": ""}]
        self.sheet = Mock()
        self.source = Mock()
        self.source.spreadsheet.worksheet.return_value = self.sheet
        self.sheet.get_all_values.return_value = [SESSION_HEADERS]

    def test_snapshot_filters_unknown_preserves_id_and_uses_thai_date(self):
        rows = session_rows("round", "29-09-2026", self.students,
                            datetime(2026, 9, 29, 18, 0, tzinfo=timezone.utc))
        self.assertEqual(rows, [["round", "29-09-2026", "001", "นักศึกษา", "2026-09-30T01:00:00+07:00", 1]])

    def test_invalid_roster_and_date_never_publish(self):
        for students in ([], [{"name": "Unknown", "student_id": ""}],
                         [{"name": "", "student_id": "1"}],
                         [{"name": "A", "student_id": "1"}, {"name": "B", "student_id": "1"}]):
            with self.subTest(students=students), self.assertRaises(ValueError):
                publish_session(self.source, "round", "29-09-2026", students)
        with self.assertRaises(ValueError):
            publish_session(self.source, "round", "31-09-2026", self.students)
        self.source.spreadsheet.worksheet.assert_not_called()

    def test_uncertain_append_retry_does_not_duplicate_round(self):
        def append(rows, **kwargs):
            self.sheet.get_all_values.return_value.extend([[str(v) for v in row] for row in rows])
            raise TimeoutError("Response lost")
        self.sheet.append_rows.side_effect = append
        with self.assertRaises(TimeoutError):
            publish_session(self.source, "round", "29-09-2026", self.students)
        self.assertEqual(publish_session(self.source, "round", "29-09-2026", self.students), 1)
        self.sheet.append_rows.assert_called_once()
        self.assertEqual(self.sheet.append_rows.call_args.kwargs, {"value_input_option": "RAW"})

    def test_incomplete_snapshot_is_not_silently_accepted(self):
        self.sheet.get_all_values.return_value.append(["round", "29-09-2026", "001", "นักศึกษา", "stamp", "2"])
        with self.assertRaises(ValueError):
            publish_session(self.source, "round", "29-09-2026", self.students)
        self.sheet.append_rows.assert_not_called()

    def test_end_time_is_published_and_retry_requires_same_time(self):
        publish_session(self.source, "round", "09-10-2026", self.students, "16:30")
        rows = self.sheet.append_rows.call_args.args[0]
        self.assertEqual(rows[0][6], "16:30")
        self.sheet.get_all_values.return_value += [[str(v) for v in row] for row in rows]
        self.assertEqual(publish_session(self.source, "round", "09-10-2026", self.students, "16:30"), 1)
        with self.assertRaises(ValueError):
            publish_session(self.source, "round", "09-10-2026", self.students, "17:00")

    def test_old_schema_cannot_silently_ignore_end_time(self):
        self.sheet.get_all_values.return_value = [SESSION_HEADERS[:6]]
        with self.assertRaisesRegex(ValueError, "AutoAbsence"):
            publish_session(self.source, "round", "09-10-2026", self.students, "16:30")
        self.sheet.append_rows.assert_not_called()
        self.assertEqual(publish_session(self.source, "manual", "09-10-2026", self.students), 1)

    def test_invalid_end_time_never_contacts_google(self):
        for value in ("", "9:30", "24:00", "12:60"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                publish_session(self.source, "round", "09-10-2026", self.students, value)
        self.source.spreadsheet.worksheet.assert_not_called()


if __name__ == "__main__":
    unittest.main()
