import pickle
from pathlib import Path
import tempfile
import unittest

from kru_check import AttendanceStore


class AttendanceStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "attendance.sqlite3"
        self.seed = Path(self.temp.name) / "students.pkl"
        self.seed.write_bytes(pickle.dumps([{"stu_id": "001", "name": "สมใจ ทดสอบ"}]))
        self.store = AttendanceStore(self.path, self.seed)
        self.addCleanup(lambda: self.store.close())

    def test_status_change_is_saved_once_per_student_per_day(self):
        student = self.store.rows("2026-09-14")[0]["id"]
        self.store.mark(student, "2026-09-14", "มา")
        self.store.mark(student, "2026-09-14", "มาสาย")
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM attendance").fetchone()[0], 1)
        self.store.close()
        self.store = AttendanceStore(self.path, self.seed)
        self.assertEqual(self.store.rows("2026-09-14")[0]["status"], "มาสาย")
        self.assertEqual(self.store.rows("2026-09-15")[0]["status"], "ยังไม่เช็ค")
        self.store.mark(student, "2026-09-14", None)
        self.assertEqual(self.store.rows("2026-09-14")[0]["status"], "ยังไม่เช็ค")

    def test_add_validates_required_fields_and_duplicate_id(self):
        for student_id, name in (("", "ชื่อ"), ("002", " "), ("001", "ชื่อซ้ำ")):
            with self.assertRaises(ValueError):
                self.store.add(student_id, name)
        self.store.add(" 002 ", " สมชาย ทดสอบ ")
        rows = self.store.rows("2026-09-14")
        self.assertEqual(len(rows), 2)
        self.assertIn("สมชาย ทดสอบ", [row["name"] for row in rows])

    def test_deleted_name_does_not_reappear_on_restart(self):
        original = self.seed.read_bytes()
        student = self.store.rows("2026-09-14")[0]["id"]
        self.store.mark(student, "2026-09-14", "มา")
        self.store.remove(student)
        self.store.close()
        self.store = AttendanceStore(self.path, self.seed)
        self.assertEqual(self.store.rows("2026-09-14"), [])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM attendance").fetchone()[0], 1)
        self.assertEqual(self.seed.read_bytes(), original)
        with self.assertRaises(ValueError):
            self.store.mark(student, "2026-09-14", "มาสาย")

    def test_bad_input_cannot_replace_existing_status(self):
        student = self.store.rows("2026-09-14")[0]["id"]
        self.store.mark(student, "2026-09-14", "มา")
        for day, status in (("2026-02-30", "มา"), ("2026-09-14", "invalid")):
            with self.assertRaises(ValueError):
                self.store.mark(student, day, status)
        self.assertEqual(self.store.rows("2026-09-14")[0]["status"], "มา")


if __name__ == "__main__":
    unittest.main()
