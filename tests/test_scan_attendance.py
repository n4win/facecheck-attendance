from datetime import datetime
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, Mock, patch

from attendance_sheets import HEADERS
import scanstu as scan


class TimeTests(unittest.TestCase):
    def test_cutoff_includes_whole_minute_and_no_absence_afterwards(self):
        cutoff = scan.parse_cutoff("08:30")
        for clock, expected in (("00:00:00", "ตรงเวลา"), ("08:30:00", "ตรงเวลา"),
                                ("08:30:59", "ตรงเวลา"), ("08:31:00", "มาสาย"),
                                ("09:15:01", "มาสาย"), ("23:59:59", "มาสาย")):
            self.assertEqual(scan.attendance_status(datetime.fromisoformat(f"2026-09-14T{clock}"), cutoff), expected)

    def test_custom_time_and_invalid_input(self):
        self.assertEqual(scan.attendance_status(datetime(2026, 9, 14, 13, 46), scan.parse_cutoff("13:45")), "มาสาย")
        for value in ("", "8:30", "24:00", "12:60", "08:30:00", "abcde"):
            with self.assertRaises(ValueError):
                scan.parse_cutoff(value)
        self.assertIn("ไม่มีช่วงมาสาย", scan.time_description(scan.parse_cutoff("23:59")))


class SelectedDateTests(unittest.TestCase):
    def test_camera_failure_never_opens_a_cloud_round(self):
        app = scan.FaceAttendanceApp.__new__(scan.FaceAttendanceApp)
        app.video = None
        app.start_failed, app.submit = Mock(), Mock()
        with patch("cv2.CascadeClassifier") as detector, patch("cv2.VideoCapture") as video:
            detector.return_value.empty.return_value = False
            video.return_value.isOpened.return_value = False
            app.open_camera(([], {"A": "001"}, Mock()))
        app.submit.assert_not_called()
        app.start_failed.assert_called_once()
        video.return_value.release.assert_called_once()

    def test_scan_waits_for_successful_cloud_round_registration(self):
        app = scan.FaceAttendanceApp.__new__(scan.FaceAttendanceApp)
        app.video = None
        app.notice, app.sheets, app.submit = Mock(), Mock(), Mock()
        app.begin_scanning = Mock()
        app.round_id, app.session_day = "round", "29-09-2026"
        app.end_time = scan.parse_cutoff("17:00")
        with patch("cv2.CascadeClassifier") as detector, patch("cv2.VideoCapture"):
            detector.return_value.empty.return_value = False
            app.open_camera(([], {"A": "001"}, Mock()))
        app.begin_scanning.assert_not_called()
        args = app.submit.call_args.args
        self.assertEqual(args[3:], ("round", "29-09-2026", [{"name": "A", "student_id": "001"}], "17:00"))
        args[1](1)
        app.begin_scanning.assert_called_once_with([])

    def test_start_loads_selected_day_and_rejects_invalid_date_before_writing(self):
        app = scan.FaceAttendanceApp.__new__(scan.FaceAttendanceApp)
        app.date_var = Mock()
        app.date_var.get.return_value = "2026-09-14"
        app.cutoff_var = Mock()
        app.cutoff_var.get.return_value = "08:30"
        app.end_time_var = Mock()
        app.end_time_var.get.return_value = "17:00"
        app.root, app.notice, app.start_button = Mock(), Mock(), Mock()
        app.date_entry, app.today_button, app.submit = Mock(), Mock(), Mock()
        with tempfile.TemporaryDirectory() as folder, patch.object(scan, "OUTBOX", Path(folder) / "pending.json"), patch.object(scan, "write_json") as write, patch.object(scan.messagebox, "showerror") as error:
            app.start()
            self.assertEqual(app.similarity_threshold, 0.40)
            write.assert_called_once_with(scan.SETTINGS, {"on_time_until": "08:30", "similarity_threshold": 0.40, "class_end_time": "17:00"})
            self.assertEqual(app.submit.call_args.args[-1], "14-09-2026")
            app.date_entry.configure.assert_called_with(state="disabled")
            app.start_failed(RuntimeError("offline"))
            app.date_entry.configure.assert_called_with(state="normal")
            write.reset_mock()
            app.submit.reset_mock()
            app.date_var.get.return_value = "2026-02-30"
            app.start()
            error.assert_called_once()
            write.assert_not_called()
            app.submit.assert_not_called()

    def test_date_validation_and_sheet_format(self):
        self.assertEqual(scan.parse_attendance_date(" 2026-09-29 "), "29-09-2026")
        self.assertEqual(scan.parse_attendance_date("2024-02-29"), "29-02-2024")
        for value in ("", "2026-02-29", "2026-04-31", "2026-13-01", "29-09-2026", "2026-9-1"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                scan.parse_attendance_date(value)

    def test_scan_records_selected_date_with_actual_scan_time_and_deduplicates(self):
        app = scan.FaceAttendanceApp.__new__(scan.FaceAttendanceApp)
        app.closed = False
        app.session_day = "14-09-2026"
        app.students = {"นักศึกษา": "001"}
        app.saved, app.pending, app.errors = {}, {}, {}
        app.annotation_key = None
        app.cutoff = scan.parse_cutoff("08:30")
        app.similarity_threshold = 0.6
        app.video = Mock()
        app.video.read.return_value = (True, MagicMock())
        app.cv2 = Mock()
        app.cv2.Laplacian.return_value.var.return_value = 100
        app.detector = Mock()
        app.detector.detectMultiScale.return_value = [(0, 0, 100, 100)]
        app.matcher = Mock()
        app.matcher.match.return_value = Mock(name="match", accepted=True, score=0.9)
        app.matcher.match.return_value.name = "นักศึกษา"
        app.stability = Mock()
        app.stability.observe.return_value = True
        app.Image, app.ImageTk, app.video_label = Mock(), Mock(), Mock()
        app.detected, app.notice, app.root = Mock(), Mock(), Mock()
        app.send_record, app.ask_annotation = Mock(), Mock()
        with patch.object(scan, "datetime") as clock:
            clock.now.return_value = datetime(2026, 9, 29, 8, 20)
            app.update_frame()
            row = app.send_record.call_args.args[0]
            self.assertEqual(row["DATE"], "14-09-2026")
            self.assertEqual(row["TIME"], "08:20:00")
            self.assertEqual(row["STATUS"], "ตรงเวลา")
            app.saved[scan.row_key(row)] = row
            clock.now.return_value = datetime(2026, 9, 30, 0, 1)
            app.update_frame()
        app.send_record.assert_called_once()
        app.ask_annotation.assert_not_called()
        app.stability.reset.assert_not_called()

    def test_table_uses_selected_day(self):
        app = scan.FaceAttendanceApp.__new__(scan.FaceAttendanceApp)
        app.session_day = "14-09-2026"
        row = dict(zip(HEADERS, [app.session_day, "นักศึกษา", "001", "08:20:00", "ตรงเวลา", ""]))
        other = {**row, "DATE": "29-09-2026"}
        app.saved = {scan.row_key(row): row, scan.row_key(other): other}
        app.pending, app.errors = {}, {}
        app.tree, app.summary = Mock(), Mock()
        app.tree.get_children.return_value = []
        app.render_table()
        app.tree.insert.assert_called_once()
        self.assertIn("14-09-2026", app.summary.set.call_args.args[0])


class SheetsTests(unittest.TestCase):
    def setUp(self):
        self.sheet = Mock()
        self.sheet.get_all_values.return_value = [["Date", "Name", "student_id", "Time", "Status", "Annotation"]]
        self.service = scan.ScanSheets(self.sheet)
        self.row = dict(zip(HEADERS, ["14-09-2026", "นักศึกษา", "001", "08:20:00", "ตรงเวลา", "ไม่มีหมายเหตุ"]))

    def test_append_preserves_columns_and_leading_zero_id(self):
        self.assertEqual(self.service.save_once(self.row), self.row)
        self.sheet.append_row.assert_called_once_with(list(self.row.values()), value_input_option="RAW")

    def test_unknown_never_contacts_google_sheets(self):
        for name in ("Unknown", "unknown", " UNKNOWN "):
            with self.assertRaises(ValueError):
                self.service.save_once({**self.row, "NAME": name})
        self.sheet.get_all_values.assert_not_called()
        self.sheet.append_row.assert_not_called()
        self.sheet.update.assert_not_called()

    def test_existing_manual_attendance_is_not_overwritten(self):
        existing = {**self.row, "STATUS": "มาสาย", "TIME": "08:40:00", "ANNOTATION": "รถติด"}
        self.sheet.get_all_values.return_value.append(list(existing.values()))
        self.assertEqual(self.service.save_once(self.row), existing)
        self.sheet.append_row.assert_not_called()
        self.sheet.update.assert_not_called()

    def test_old_absence_row_becomes_actual_attendance(self):
        self.sheet.get_all_values.return_value.append(list({**self.row, "STATUS": "ขาดเรียน"}.values()))
        self.service.save_once(self.row)
        self.sheet.update.assert_called_once_with(range_name="A2:F2", values=[list(self.row.values())], value_input_option="RAW")

    def test_selected_day_excludes_unknown_other_dates_and_includes_absence(self):
        absent = {**self.row, "STUDENT_ID": "002", "STATUS": "ขาดเรียน", "TIME": "-"}
        self.sheet.get_all_values.return_value.extend([
            list(self.row.values()), list({**self.row, "NAME": "Unknown"}.values()),
            list({**self.row, "DATE": "13-09-2026"}.values()),
            list(absent.values())])
        self.assertEqual(self.service.today("14-09-2026"), [self.row, absent])

    def test_uncertain_write_can_be_retried_without_duplicate(self):
        def append(values, **kwargs):
            self.sheet.get_all_values.return_value.append(values)
            raise TimeoutError("Response lost")
        self.sheet.append_row.side_effect = append
        with self.assertRaises(TimeoutError):
            self.service.save_once(self.row)
        self.assertEqual(self.service.save_once(self.row), self.row)
        self.assertEqual(self.sheet.append_row.call_count, 1)

    def test_duplicate_rows_fail_without_writing(self):
        self.sheet.get_all_values.return_value.extend([list(self.row.values())] * 2)
        with self.assertRaises(ValueError):
            self.service.save_once(self.row)
        self.sheet.append_row.assert_not_called()


class PendingTests(unittest.TestCase):
    def test_unknown_is_not_queued_or_sent(self):
        app = scan.FaceAttendanceApp.__new__(scan.FaceAttendanceApp)
        app.submit = Mock()
        with patch.object(scan, "write_json") as write:
            for name in ("Unknown", "unknown", " UNKNOWN "):
                app.send_record({"NAME": name})
        write.assert_not_called()
        app.submit.assert_not_called()

    def test_failure_keeps_outbox_and_success_clears_it(self):
        app = scan.FaceAttendanceApp.__new__(scan.FaceAttendanceApp)
        app.saved, app.pending, app.errors, app.sending = {}, {}, {}, set()
        app.sheets, app.notice, app.render_table, app.submit = Mock(), Mock(), Mock(), Mock()
        row = dict(zip(HEADERS, ["14-09-2026", "นักศึกษา", "001", "08:31:00", "มาสาย", "รถติด"]))
        with tempfile.TemporaryDirectory() as folder, patch.object(scan, "OUTBOX", Path(folder) / "pending.json"):
            app.send_record(row)
            self.assertEqual(json.loads(scan.OUTBOX.read_text()), [row])
            self.assertEqual(app.saved, {})
            app.submit.call_args.args[2](TimeoutError("offline"))
            self.assertIn(scan.row_key(row), app.errors)
            self.assertEqual(json.loads(scan.OUTBOX.read_text()), [row])
            app.retry()
            app.submit.call_args.args[1](row)
            self.assertEqual(json.loads(scan.OUTBOX.read_text()), [])
            self.assertEqual(app.saved[scan.row_key(row)], row)
            self.assertEqual(app.pending, {})


if __name__ == "__main__":
    unittest.main()
