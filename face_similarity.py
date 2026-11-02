"""Local SFace embeddings, cosine scores and conservative attendance gating.

Legacy training data consists of 50x50 BGR face crops without landmarks.
Enrollment and query crops use the same resize path; these are not aligned
benchmark images. Thresholds must be evaluated on separate local sessions.
"""
from dataclasses import dataclass
import time
import numpy as np

from app_paths import MODEL_PATH

DEFAULT_THRESHOLD = 0.40
MIN_MARGIN = 0.08
REQUIRED_FRAMES = 5
REQUIRED_SECONDS = 0.8


def validate_threshold(value):
    score = float(value)
    if not np.isfinite(score) or not 0.4 <= score <= 0.95:
        raise ValueError("คะแนนขั้นต่ำต้องอยู่ระหว่าง 0.40 ถึง 0.95")
    return score


@dataclass
class Match:
    name: str
    score: float
    margin: float
    votes: float
    accepted: bool
    reason: str


def rank_match(features, labels, query, prediction, votes, threshold):
    similarities = np.clip(features @ query, -1.0, 1.0)
    # ค่าเฉลี่ย 3 ตัวอย่างที่ใกล้ที่สุดต่อคน ลดผลจากภาพเดียวที่บังเอิญเหมือน
    scores = []
    for name in sorted(set(labels)):
        values = np.sort(similarities[np.asarray(labels) == name])
        scores.append((name, float(np.mean(values[-min(3, len(values)):]))))
    scores.sort(key=lambda item: item[1], reverse=True)
    name, score = scores[0]
    margin = score - scores[1][1] if len(scores) > 1 else 2.0
    if name.strip().casefold() == "unknown":
        reason = "Unknown — ไม่บันทึก"
    elif score < threshold:
        reason = "คะแนนยังไม่ถึงเกณฑ์"
    elif margin < MIN_MARGIN:
        reason = "คะแนนใกล้เคียงหลายคน"
    elif name != prediction or votes < 0.8:
        reason = "ผล KNN ยังไม่สอดคล้องกัน"
    else:
        reason = "ผ่านเกณฑ์ความใกล้เคียง"
    return Match(name, score, margin, votes, reason == "ผ่านเกณฑ์ความใกล้เคียง", reason)


class FaceMatcher:
    def __init__(self, faces, labels, threshold=DEFAULT_THRESHOLD):
        import cv2
        from sklearn.neighbors import KNeighborsClassifier
        if not MODEL_PATH.is_file():
            raise ValueError("ไม่พบโมเดล SFace ในโฟลเดอร์ models")
        self.cv2 = cv2
        self.model = cv2.FaceRecognizerSF_create(str(MODEL_PATH), "")
        self.threshold = validate_threshold(threshold)
        self.labels = list(labels)
        samples = np.asarray(faces)
        if not len(samples) or len(samples) != len(labels) or samples.shape[1:] != (7500,):
            raise ValueError("ข้อมูลใบหน้าต้องเป็นภาพ BGR ขนาด 50×50 และมีจำนวนตรงกับชื่อ")
        self.features = np.stack([self.embedding(sample.reshape(50, 50, 3)) for sample in samples])
        self.knn = KNeighborsClassifier(n_neighbors=min(5, len(labels)), metric="cosine", algorithm="brute")
        self.knn.fit(self.features, self.labels)

    def embedding(self, crop):
        # Match enrollment preprocessing exactly; original data is 50x50.
        small = self.cv2.resize(np.asarray(crop, dtype=np.uint8), (50, 50))
        image = self.cv2.resize(small, (112, 112))
        vector = self.model.feature(image).reshape(-1).astype(np.float32)
        norm = np.linalg.norm(vector)
        if not np.isfinite(norm) or norm < 1e-8:
            raise ValueError("ไม่สามารถคำนวณลักษณะใบหน้าได้")
        return vector / norm

    def match(self, crop):
        query = self.embedding(crop)
        probabilities = self.knn.predict_proba(query.reshape(1, -1))[0]
        best = int(np.argmax(probabilities))
        return rank_match(self.features, self.labels, query, str(self.knn.classes_[best]),
                          float(probabilities[best]), self.threshold)


class StableMatch:
    def __init__(self):
        self.reset()

    def reset(self):
        self.name = None
        self.box = None
        self.count = 0
        self.started = None
        self.last = None

    def observe(self, name, accepted, box, now=None):
        now = time.monotonic() if now is None else now
        if not accepted:
            self.reset()
            return False
        continuous = self.name == name and self.last is not None and 0 <= now - self.last <= 1.0
        if continuous:
            x, y, w, h = box
            a, b, c, d = self.box
            overlap = max(0, min(x+w, a+c)-max(x, a)) * max(0, min(y+h, b+d)-max(y, b))
            union = w*h + c*d - overlap
            continuous = union > 0 and overlap / union >= 0.3
        if not continuous:
            self.reset()
            self.name, self.started = name, now
        self.box, self.last = box, now
        self.count += 1
        return self.count >= REQUIRED_FRAMES and now - self.started >= REQUIRED_SECONDS
