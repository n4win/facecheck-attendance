import pickle
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from studata import FILES, StudentStore


class StudentStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.store = StudentStore(self.directory)
        self.first = {"name": "นักเรียนหนึ่ง", "stu_id": "001"}
        self.second = {"name": "นักเรียนสอง", "stu_id": "002"}
        self.students = [self.first, {"name": "Unknown", "stu_id": ""}, self.second,
                         {"name": "ยังไม่มีใบหน้า", "stu_id": "003"}]
        self.labels = ["Unknown", self.first["name"], self.second["name"], self.first["name"], "Unknown"]
        self.faces = np.arange(15).reshape(5, 3)
        self.write(self.students, self.labels, self.faces)

    def write(self, *values):
        for name, value in zip(FILES, values):
            (self.directory / name).write_bytes(pickle.dumps(value))

    def test_only_registered_students_are_visible(self):
        self.assertEqual(self.store.rows(), [self.first, self.second])

    def test_edit_updates_all_labels_preserving_face_samples(self):
        self.store.change(self.first, "ชื่อใหม่", "0009")
        students, labels, faces, _ = self.store.load()
        self.assertEqual(students[0], {"name": "ชื่อใหม่", "stu_id": "0009"})
        self.assertEqual(labels, ["Unknown", "ชื่อใหม่", self.second["name"], "ชื่อใหม่", "Unknown"])
        np.testing.assert_array_equal(faces, self.faces)

    def test_delete_preserves_unknown_and_other_students(self):
        self.store.change(self.first)
        students, labels, faces, _ = self.store.load()
        self.assertNotIn(self.first, students)
        self.assertEqual(labels, ["Unknown", self.second["name"], "Unknown"])
        np.testing.assert_array_equal(faces, self.faces[[0, 2, 4]])

    def test_invalid_edits_do_not_change_files(self):
        before = {name: (self.directory / name).read_bytes() for name in FILES}
        for name, student_id in (("", "009"), ("ใหม่", ""), ("ใหม่", "002"), ("Unknown", "009"), (self.second["name"], "009")):
            with self.assertRaises(ValueError):
                self.store.change(self.first, name, student_id)
        self.assertEqual(before, {name: (self.directory / name).read_bytes() for name in FILES})

    def test_duplicate_names_are_not_deleted_ambiguously(self):
        self.write(self.students + [{"name": self.first["name"], "stu_id": "004"}], self.labels, self.faces)
        with self.assertRaises(ValueError):
            self.store.change(self.first)

    def test_unknown_only_without_roster_is_empty(self):
        self.write([], ["unknown"], np.zeros((1, 3)))
        (self.directory / "student_data.pkl").unlink()
        self.assertEqual(self.store.rows(), [])

    def test_changed_selection_does_not_overwrite_newer_record(self):
        self.store.change(self.first, "เปลี่ยนแล้ว", "001")
        with self.assertRaises(ValueError):
            self.store.change(self.first)

    def test_failed_replace_restores_original_files(self):
        before = {name: (self.directory / name).read_bytes() for name in FILES}
        original_replace = Path.replace

        def fail_second(path, target):
            if Path(target).name == "names.pkl":
                raise OSError("จำลองการเขียนล้มเหลว")
            return original_replace(path, target)

        with patch.object(Path, "replace", fail_second), self.assertRaises(OSError):
            self.store.change(self.first, "ใหม่", "009")
        self.assertEqual(before, {name: (self.directory / name).read_bytes() for name in FILES})


if __name__ == "__main__":
    unittest.main()
