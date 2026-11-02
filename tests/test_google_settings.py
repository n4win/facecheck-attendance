import json
import os
from pathlib import Path
import stat
import tempfile
import unittest
from unittest.mock import Mock, patch

import attendance_sheets
from attendance_sheets import AttendanceSheets, HEADERS, SIGN_IN_REQUIRED, spreadsheet_url
import google_settings
import scanstu as scan


class SettingsCase(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.dir = Path(folder.name)
        for name, value in (("SETTINGS_PATH", self.dir / "google_settings.json"), ("KEY_PATH", self.dir / "key.json")):
            patcher = patch.object(google_settings, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)
        self.key = self.dir / "download.json"
        self.key.write_text(json.dumps({"type": "service_account", "client_email": "bot@example.test", "private_key": "secret"}))


class GoogleSettingsTests(SettingsCase):
    def test_attendance_requires_sign_in_and_never_writes_a_local_copy(self):
        self.assertIsNone(google_settings.load())
        self.assertFalse(google_settings.absence_summary_enabled())
        with self.assertRaisesRegex(ValueError, SIGN_IN_REQUIRED):
            AttendanceSheets().connect()
        with self.assertRaisesRegex(ValueError, SIGN_IN_REQUIRED):
            scan.ScanSheets().today("14-09-2026")
        self.assertEqual([path.name for path in self.dir.iterdir()], ["download.json"])

    def test_signed_in_account_opens_its_own_sheet(self):
        google_settings.save_account("sheet-id", "teacher@example.test", True)
        with patch("google_auth.open_worksheet", return_value="sheet") as opener:
            self.assertEqual(AttendanceSheets().connect(), "sheet")
        opener.assert_called_once_with("sheet-id")
        self.assertTrue(google_settings.absence_summary_enabled())

    def test_sign_in_replaces_key_mode_and_removes_the_key_copy(self):
        google_settings.save("ชีต", self.key)
        google_settings.save_account("sheet-id", "teacher@example.test")
        self.assertFalse(google_settings.KEY_PATH.exists())
        self.assertEqual(google_settings.load()["spreadsheet_id"], "sheet-id")

    def test_spreadsheet_link_for_each_mode(self):
        self.assertIsNone(spreadsheet_url(None))
        self.assertIsNone(spreadsheet_url({"spreadsheet": "ชื่อชีต"}))
        self.assertEqual(spreadsheet_url({"spreadsheet": "https://docs.google.com/x"}), "https://docs.google.com/x")
        self.assertIn("/d/abc/", spreadsheet_url({"spreadsheet_id": "abc"}))

    def test_save_copies_key_privately_and_round_trips(self):
        google_settings.save(" ชีตของฉัน ", self.key, auto_absence=True)
        self.assertEqual(google_settings.load()["spreadsheet"], "ชีตของฉัน")
        self.assertTrue(google_settings.absence_summary_enabled())
        self.assertEqual(google_settings.key_email(google_settings.KEY_PATH), "bot@example.test")
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(google_settings.KEY_PATH.stat().st_mode), 0o600)

    def test_wrong_key_file_is_rejected_and_nothing_is_saved(self):
        for content in ("not json", json.dumps({"type": "authorized_user"})):
            self.key.write_text(content)
            with self.assertRaises(ValueError):
                google_settings.save("ชีต", self.key)
        self.assertFalse(google_settings.is_configured())
        self.assertFalse(google_settings.KEY_PATH.exists())

    def test_broken_settings_fail_loudly_instead_of_writing_locally(self):
        google_settings.save("ชีต", self.key)
        google_settings.KEY_PATH.unlink()
        with self.assertRaises(ValueError):
            AttendanceSheets().connect()
        google_settings.SETTINGS_PATH.write_text("{broken")
        with self.assertRaises(ValueError):
            AttendanceSheets().connect()

    def test_clear_removes_key_copy(self):
        google_settings.save("ชีต", self.key)
        google_settings.clear()
        self.assertFalse(google_settings.is_configured())
        self.assertFalse(google_settings.KEY_PATH.exists())
        self.assertTrue(self.key.exists())

    def test_configured_sheet_is_opened_with_saved_key(self):
        google_settings.save("ชีตของฉัน", self.key)
        with patch.object(attendance_sheets, "open_google_worksheet", return_value="sheet") as opener:
            self.assertEqual(AttendanceSheets().connect(), "sheet")
        opener.assert_called_once_with("ชีตของฉัน", google_settings.KEY_PATH)

    def test_check_is_read_only_and_reports_absence_tab(self):
        sheet = Mock()
        sheet.row_values.return_value = HEADERS
        sheet.spreadsheet.worksheets.return_value = [Mock(title="Attendance_Sessions")]
        with patch.object(attendance_sheets, "open_google_worksheet", return_value=sheet):
            self.assertTrue(attendance_sheets.check_google_sheet("ชีต", self.key))
            sheet.row_values.return_value = ["unexpected"]
            with self.assertRaises(ValueError):
                attendance_sheets.check_google_sheet("ชีต", self.key)
        self.assertEqual([call[0] for call in sheet.method_calls if call[0] in ("update", "append_row", "delete_rows", "append_rows")], [])


class OpenSessionTests(SettingsCase):
    def test_no_absence_system_skips_session(self):
        with patch("attendance_sessions.publish_session") as publish:
            google_settings.save("ชีต", self.key, auto_absence=False)
            self.assertEqual(AttendanceSheets(Mock()).open_session("r", "14-09-2026", []), 0)
        publish.assert_not_called()

    def test_installed_absence_system_still_publishes(self):
        google_settings.save("ชีต", self.key, auto_absence=True)
        sheet = Mock()
        with patch("attendance_sessions.publish_session", return_value=3) as publish:
            self.assertEqual(AttendanceSheets(sheet).open_session("r", "14-09-2026", [], "17:00"), 3)
        publish.assert_called_once_with(sheet, "r", "14-09-2026", [], end_time="17:00")


class FirstRunTests(unittest.TestCase):
    def test_scan_without_registered_faces_gives_clear_message(self):
        app = scan.FaceAttendanceApp.__new__(scan.FaceAttendanceApp)
        app.sheets, app.similarity_threshold = Mock(), 0.4
        app.sheets.today.return_value = []
        with tempfile.TemporaryDirectory() as folder, patch.object(scan, "DATA_DIR", Path(folder)):
            with self.assertRaisesRegex(ValueError, "ลงทะเบียน"):
                app.prepare_session("14-09-2026")


if __name__ == "__main__":
    unittest.main()
