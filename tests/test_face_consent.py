from contextlib import closing
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import Mock, patch

import add_face_student
import face_consent


class FaceConsentTests(unittest.TestCase):
    def test_decline_does_not_open_camera_or_close_registration(self):
        window, label, camera = Mock(), Mock(), Mock()
        with patch.object(add_face_student, "window", window, create=True), \
             patch.object(add_face_student, "error_label", label, create=True), \
             patch.object(add_face_student, "request_face_consent", return_value=False), \
             patch.dict("sys.modules", {"cv2": camera}):
            add_face_student.start_face_capture("ชื่อทดสอบ", "001")
        camera.VideoCapture.assert_not_called()
        window.destroy.assert_not_called()

    def test_camera_is_opened_only_after_consent(self):
        events = []
        window, camera = Mock(), Mock()
        camera.VideoCapture.side_effect = lambda *_: events.append("camera") or Mock(isOpened=lambda: False)
        with patch.object(add_face_student, "window", window, create=True), \
             patch.object(add_face_student, "name_entry", Mock(), create=True), \
             patch.object(add_face_student, "error_label", Mock(), create=True), \
             patch.object(add_face_student.os.path, "exists", return_value=False), \
             patch.object(add_face_student, "request_face_consent", side_effect=lambda *_: events.append("consent") or True), \
             patch.dict("sys.modules", {"cv2": camera, "numpy": Mock()}):
            add_face_student.start_face_capture("ชื่อทดสอบ", "001")
        self.assertEqual(events, ["consent", "camera"])
        window.deiconify.assert_called_once()
        camera.destroyAllWindows.assert_called_once()

    def test_success_restores_empty_form_and_requests_consent_for_each_student(self):
        window, name_entry, id_entry, label = Mock(), Mock(), Mock(), Mock()
        with patch.object(add_face_student, "window", window, create=True), \
             patch.object(add_face_student, "name_entry", name_entry, create=True), \
             patch.object(add_face_student, "stu_id_entry", id_entry, create=True), \
             patch.object(add_face_student, "error_label", label, create=True), \
             patch.object(add_face_student, "request_face_consent", return_value=True) as consent, \
             patch.object(add_face_student, "capture_and_save") as capture:
            add_face_student.start_face_capture("คนแรก", "001")
            add_face_student.start_face_capture("คนถัดไป", "002")
        self.assertEqual(consent.call_count, 2)
        self.assertEqual(capture.call_count, 2)
        self.assertEqual(window.deiconify.call_count, 2)
        self.assertEqual(name_entry.delete.call_count, 2)
        self.assertEqual(id_entry.delete.call_count, 2)
        self.assertEqual(name_entry.focus_set.call_count, 2)
        window.destroy.assert_not_called()

    def test_capture_failure_restores_form_without_clearing_input(self):
        window, name_entry, id_entry, label = Mock(), Mock(), Mock(), Mock()
        with patch.object(add_face_student, "window", window, create=True), \
             patch.object(add_face_student, "name_entry", name_entry, create=True), \
             patch.object(add_face_student, "stu_id_entry", id_entry, create=True), \
             patch.object(add_face_student, "error_label", label, create=True), \
             patch.object(add_face_student, "request_face_consent", return_value=True), \
             patch.object(add_face_student, "capture_and_save", side_effect=RuntimeError("กล้องขัดข้อง")):
            add_face_student.start_face_capture("คนแรก", "001")
        window.deiconify.assert_called_once()
        window.destroy.assert_not_called()
        name_entry.delete.assert_not_called()
        id_entry.delete.assert_not_called()
        self.assertIn("กล้องขัดข้อง", label.config.call_args.kwargs["text"])

    def test_notice_and_consent_evidence_preserve_exact_text(self):
        settings = {"controller": "ผู้ควบคุมข้อมูลทดสอบ", "contact": "ติดต่อ ณ ห้องโครงงาน",
                    "retention": "จนกว่าจะสิ้นสุดโครงการ", "access": "ผู้รับผิดชอบโครงการ"}
        notice = face_consent.consent_text(settings, "ชื่อทดสอบ", "001")
        for expected in (settings["controller"], settings["retention"], "เพื่อการศึกษา", "ถอนความยินยอม", "Google Sheets"):
            self.assertIn(expected, notice)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "consents.sqlite3"
            face_consent.record_consent("ชื่อทดสอบ", "001", notice, path)
            with closing(sqlite3.connect(path)) as db:
                row = db.execute("SELECT student_id, notice, policy_version, decision, consented_at FROM consents").fetchone()
            self.assertEqual(row[:4], ("001", notice, face_consent.POLICY_VERSION, "explicitly_agreed"))
            self.assertTrue(row[4])

    def test_incomplete_controller_details_are_not_presented_as_valid(self):
        with self.assertRaises(ValueError):
            face_consent.consent_text({"controller": "ผู้รับผิดชอบ"}, "ชื่อ", "001")


if __name__ == "__main__":
    unittest.main()
