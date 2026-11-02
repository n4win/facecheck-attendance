import unittest
from unittest.mock import Mock

from attendance_sheets import AttendanceSheets, HEADERS
import test_manual_attendance


class SheetsTests(unittest.TestCase):
    def setUp(self):
        self.sheet = Mock()
        self.sheet.get_all_values.return_value = [HEADERS]
        self.sync = AttendanceSheets(self.sheet)
        self.item = dict(day="2026-09-14", student_id="001", name="สมใจ", status="มา", updated_at="08:00:00")

    def test_new_attendance_matches_face_columns_and_preserves_id(self):
        self.sync.send(self.item)
        self.sheet.append_row.assert_called_once_with(
            ["14-09-2026", "สมใจ", "001", "08:00:00", "ตรงเวลา", "ไม่มีหมายเหตุ"], value_input_option="RAW")

    def test_actual_sheet_header_capitalization_is_supported(self):
        self.sheet.get_all_values.return_value = [["Date", "Name", "student_id", "Time", "Status", "Annotation"]]
        self.sync.send(self.item)
        self.sheet.append_row.assert_called_once()
        self.sheet.update.assert_not_called()

    def test_existing_face_row_is_updated_and_annotation_preserved(self):
        self.sheet.get_all_values.return_value = [HEADERS, ["14-09-2026", "สมใจ", "001", "07:00:00", "ตรงเวลา", "รถติด"]]
        self.item["status"] = "มาสาย"
        self.sync.send(self.item)
        self.sheet.append_row.assert_not_called()
        self.sheet.update.assert_called_once_with(range_name="A2:F2", values=[
            ["14-09-2026", "สมใจ", "001", "08:00:00", "มาสาย", "รถติด"]], value_input_option="RAW")

    def test_same_name_different_id_is_not_overwritten(self):
        self.sheet.get_all_values.return_value = [HEADERS, ["14-09-2026", "สมใจ", "002"]]
        self.sync.send(self.item)
        self.sheet.append_row.assert_called_once()
        self.sheet.update.assert_not_called()

    def test_header_mismatch_and_duplicates_do_not_write(self):
        for values in ([["unexpected"]], [HEADERS, ["14-09-2026", "สมใจ", "001"], ["14-09-2026", "สมใจ", "001"]]):
            self.sheet.get_all_values.return_value = values
            with self.assertRaises(ValueError):
                self.sync.send(self.item)
        self.sheet.append_row.assert_not_called()
        self.sheet.update.assert_not_called()

    def test_cancel_only_matching_student_and_date(self):
        self.sheet.get_all_values.return_value = [HEADERS, ["13-09-2026", "สมใจ", "001"], ["14-09-2026", "สมใจ", "001"]]
        self.item["status"] = None
        self.sync.send(self.item)
        self.sheet.delete_rows.assert_called_once_with(3)

    def test_retry_after_ambiguous_append_updates_instead_of_appending(self):
        def append(values, **kwargs):
            self.sheet.get_all_values.return_value.append(values)
            raise TimeoutError("Response lost after successful write")
        self.sheet.append_row.side_effect = append
        with self.assertRaises(TimeoutError):
            self.sync.send(self.item)
        self.sync.send(self.item)
        self.assertEqual(self.sheet.append_row.call_count, 1)
        self.sheet.update.assert_called_once()


class QueueTests(unittest.TestCase):
    setUp = test_manual_attendance.AttendanceStoreTests.setUp
    def test_pending_survives_restart_and_old_ack_cannot_drop_new_status(self):
        student = self.store.rows("2026-09-14")[0]["id"]
        self.store.mark(student, "2026-09-14", "มา")
        old = self.store.pending()[0]
        self.store.mark(student, "2026-09-14", "มาสาย")
        self.store.acknowledge(old)
        self.store.close()
        from kru_check import AttendanceStore
        self.store = AttendanceStore(self.path, self.seed)
        self.assertEqual(self.store.pending()[0]["status"], "มาสาย")
        self.store.acknowledge(self.store.pending()[0])
        self.assertEqual(self.store.pending(), [])

    def test_cancel_is_queued_even_though_local_attendance_is_removed(self):
        student = self.store.rows("2026-09-14")[0]["id"]
        self.store.mark(student, "2026-09-14", "มา")
        self.store.mark(student, "2026-09-14", None)
        self.assertEqual(len(self.store.pending()), 1)
        self.assertIsNone(self.store.pending()[0]["status"])
