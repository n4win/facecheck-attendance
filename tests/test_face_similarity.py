import unittest
import numpy as np
from unittest.mock import Mock, patch
from datetime import datetime
from PIL import Image
import cv2
import scanstu
from face_similarity import Match
from face_similarity import rank_match, StableMatch, validate_threshold


class SimilarityTests(unittest.TestCase):
    def decide(self, first=0.9, second=0.2, prediction="A", votes=1.0, label="A"):
        features = np.array([[first, np.sqrt(1-first**2)], [second, np.sqrt(1-second**2)]])
        return rank_match(features, [label, "B"], np.array([1., 0.]), prediction, votes, 0.6)

    def test_only_high_clear_and_consistent_match_is_accepted(self):
        self.assertTrue(self.decide().accepted)
        self.assertFalse(self.decide(first=0.59).accepted)
        self.assertFalse(self.decide(second=0.86).accepted)
        self.assertFalse(self.decide(prediction="B").accepted)
        self.assertFalse(self.decide(votes=0.6).accepted)
        self.assertFalse(self.decide(label="Unknown", prediction="Unknown").accepted)

    def test_one_similar_sample_is_not_enough(self):
        features = np.array([[1., 0.], [0.2, 0.98], [0.2, 0.98]])
        result = rank_match(features, ["A"]*3, np.array([1., 0.]), "A", 1., .6)
        self.assertFalse(result.accepted)

    def test_threshold_validation(self):
        self.assertEqual(validate_threshold("0.70"), .7)
        for value in ("nan", "inf", "abc", "1", "0.1"):
            with self.assertRaises(ValueError):
                validate_threshold(value)


class StabilityTests(unittest.TestCase):
    def test_requires_frames_and_duration(self):
        gate = StableMatch()
        for now in (0., .1, .2, .3, .4):
            self.assertFalse(gate.observe("A", True, (0, 0, 100, 100), now))
        self.assertTrue(gate.observe("A", True, (0, 0, 100, 100), .9))

    def test_rejection_identity_change_jump_and_time_gap_reset(self):
        for next_name, accepted, box, stamp in (("A", False, (0,0,100,100), .9),
                                                ("B", True, (0,0,100,100), .9),
                                                ("A", True, (300,300,100,100), .9),
                                                ("A", True, (0,0,100,100), 3.0)):
            gate = StableMatch()
            for now in (0., .2, .4, .6):
                gate.observe("A", True, (0, 0, 100, 100), now)
            self.assertFalse(gate.observe(next_name, accepted, box, stamp))
            self.assertLessEqual(gate.count, 1)

    def test_reset_after_no_face_prevents_accumulating_old_frames(self):
        gate = StableMatch()
        for now in (0., .2, .4, .6):
            gate.observe("A", True, (0,0,100,100), now)
        gate.reset()
        self.assertFalse(gate.observe("A", True, (0,0,100,100), .9))


class ScannerGateTests(unittest.TestCase):
    def make_app(self, accepted=True, boxes=None):
        app = scanstu.FaceAttendanceApp.__new__(scanstu.FaceAttendanceApp)
        app.closed = False
        app.cv2, app.Image, app.ImageTk = cv2, Image, Mock()
        frame = np.random.default_rng(1).integers(0, 255, (160,160,3), dtype=np.uint8)
        app.video = Mock()
        app.video.read.side_effect = lambda: (True, frame.copy())
        app.detector = Mock()
        app.detector.detectMultiScale.return_value = [(20,20,100,100)] if boxes is None else boxes
        app.matcher = Mock()
        app.matcher.match.return_value = Match("A", .9 if accepted else .4, .2, 1., accepted, "ทดสอบ")
        app.stability = StableMatch()
        app.students = {"A": "001"}
        app.saved, app.pending, app.errors = {}, {}, {}
        app.annotation_key, app.annotation = None, None
        app.similarity_threshold = .6
        app.cutoff = scanstu.parse_cutoff("23:59")
        app.session_day = datetime.now().strftime("%d-%m-%Y")
        app.root, app.detected, app.video_label, app.notice = Mock(), Mock(), Mock(), Mock()
        app.send_record, app.ask_annotation = Mock(), Mock()
        return app

    def test_scanner_sends_only_after_stable_pass(self):
        app = self.make_app()
        with patch("face_similarity.time.monotonic", side_effect=[0., .2, .4, .6, .9]):
            for _ in range(4):
                app.update_frame()
                app.send_record.assert_not_called()
            app.update_frame()
        app.send_record.assert_called_once()

    def test_low_score_or_multiple_faces_never_send(self):
        for app in (self.make_app(False), self.make_app(boxes=[(0,0,80,80),(80,80,80,80)])):
            for _ in range(6):
                app.update_frame()
            app.send_record.assert_not_called()
            app.ask_annotation.assert_not_called()

    def test_confirmed_face_can_correct_an_automatic_absence(self):
        app = self.make_app()
        app.saved[(app.session_day, "001")] = {"STATUS": "ขาดเรียน"}
        with patch("face_similarity.time.monotonic", side_effect=[0., .2, .4, .6, .9]):
            for _ in range(5):
                app.update_frame()
        app.send_record.assert_called_once()
        row = app.send_record.call_args.args[0]
        self.assertEqual(row["DATE"], app.session_day)
        self.assertEqual(row["STATUS"], "ตรงเวลา")


if __name__ == "__main__":
    unittest.main()
