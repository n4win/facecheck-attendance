import pickle
from pathlib import Path
import tempfile
import unittest
import numpy as np

from kru_check import AttendanceStore
from studata import StudentStore


class RosterSyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.student = {"name": "นักศึกษาหนึ่ง", "stu_id": "001"}
        for filename, value in (("student_data.pkl", [self.student]),
                                ("names.pkl", ["Unknown", self.student["name"], self.student["name"]]),
                                ("faces_data.pkl", np.zeros((3, 4)))):
            (self.directory / filename).write_bytes(pickle.dumps(value))
        self.roster = StudentStore(self.directory)
        self.store = AttendanceStore(self.directory / "manual.sqlite3", roster=self.roster)
        self.addCleanup(self.store.close)

    def test_name_and_id_change_keep_attendance_on_same_person(self):
        before = self.store.rows("2026-09-14")[0]
        self.store.mark(before["id"], "2026-09-14", "มา")
        self.roster.change(self.roster.rows()[0], "ชื่อใหม่", "0002")
        after = self.store.rows("2026-09-14")[0]
        self.assertEqual(after["id"], before["id"])
        self.assertEqual((after["name"], after["student_id"], after["status"]), ("ชื่อใหม่", "0002", "มา"))

    def test_delete_hides_student_but_preserves_history(self):
        before = self.store.rows("2026-09-14")[0]
        self.store.mark(before["id"], "2026-09-14", "มาสาย")
        self.roster.change(self.roster.rows()[0])
        self.assertEqual(self.store.rows("2026-09-14"), [])
        self.assertEqual(self.store.db.execute("SELECT COUNT(*) FROM attendance").fetchone()[0], 1)
        with self.assertRaises(ValueError):
            self.store.mark(before["id"], "2026-09-14", "มา")

    def test_initial_migration_corrects_old_name_and_hides_stale_entries(self):
        self.store.db.execute("DELETE FROM students")
        self.store.db.execute("INSERT INTO students(student_id, name) VALUES ('001', 'ชื่อเก่า')")
        self.store.db.execute("INSERT INTO students(student_id, name) VALUES ('999', 'Unknown')")
        self.store.db.commit()
        self.store.roster_stamp = None
        rows = self.store.rows("2026-09-14")
        self.assertEqual([(r["student_id"], r["name"]) for r in rows], [("001", self.student["name"])])

    def test_manual_only_entries_survive_roster_refresh(self):
        self.store.add("999", "เช็คมือเท่านั้น")
        self.roster.change(self.roster.rows()[0], "เปลี่ยนชื่อ", "001")
        self.assertEqual(len(self.store.rows("2026-09-14")), 2)

    def test_new_registered_student_appears_on_next_refresh(self):
        students, names, faces, raw = self.roster.load()
        students.append({"name": "นักศึกษาใหม่", "stu_id": "009"})
        self.roster.save((students, names + ["นักศึกษาใหม่"], np.vstack([faces, np.zeros((1, 4))])), raw)
        self.assertEqual({r["student_id"] for r in self.store.rows("2026-09-14")}, {"001", "009"})


if __name__ == "__main__":
    unittest.main()
