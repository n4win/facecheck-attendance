# Local face similarity model

`face_recognition_sface_2021dec.onnx` is OpenCV Zoo's SFace model:
https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface

License: Apache 2.0, included as `SFace-LICENSE`.
The model runs locally. No facial images are uploaded to a recognition service.

The scanner converts the existing 50×50 BGR face crops into normalized SFace
embeddings and uses KNN with cosine distance (k up to 5). Each person's similarity
score is the mean of their three highest sample similarities. Unknown samples
remain negative examples. A match must pass all of these checks:

- Cosine score at least the configured threshold (initial value 0.60).
- Lead over the next identity of at least 0.08.
- KNN selects the same identity with at least 80% of votes.
- One clear face, at least 80×80 pixels, sharpness variance at least 35.
- Same identity and overlapping face location for at least five consecutive
  accepted frames spanning 0.8 seconds, without a gap longer than one second.

These are initial operating parameters, not calibrated accuracy guarantees.
The legacy crops have no landmarks and are not aligned SFace benchmark inputs.
Resizing them to 112×112 cannot restore lost image detail. Evaluate enrollment
and test images from different capture sessions, including unenrolled people,
before deciding the threshold. Measure false acceptance and false rejection;
do not interpret cosine scores as percentages or choose thresholds from
self-matching enrollment images. Landmark-aligned, higher-resolution enrollment
is a future improvement; the existing registration files remain compatible.
