import tkinter as tk
from tkinter import ttk
from ui_theme import ResponsivePanel, wrap_labels, apply_theme, page_header, window_size
import pickle
import os
from app_paths import DATA_DIR, FACE_DETECTOR_PATH
from face_consent import request_face_consent

# ==============================
# START FACE CAPTURE FUNCTION
# ==============================
def start_face_capture(name, stu_id):
    if not request_face_consent(window, name, stu_id):
        error_label.config(text="ไม่ได้เริ่มบันทึกใบหน้า: ยังไม่ได้ให้ความยินยอม", foreground="red")
        return

    window.withdraw()
    try:
        capture_and_save(name, stu_id)
    except Exception as exc:
        error_label.config(text=f"บันทึกไม่สำเร็จ: {exc}", foreground="red")
    else:
        name_entry.delete(0, tk.END)
        stu_id_entry.delete(0, tk.END)
        error_label.config(text=f"บันทึกใบหน้าของ {name} สำเร็จ\nกรอกข้อมูลนักศึกษาคนถัดไปได้เลย", foreground="green")
    finally:
        window.deiconify()
        window.lift()
        name_entry.focus_set()


def capture_and_save(name, stu_id):
    import cv2
    import numpy as np

    # ตรวจรหัสก่อนเก็บภาพหรือแก้ไขไฟล์ข้อมูลใบหน้า
    if os.path.exists(DATA_DIR / 'student_data.pkl'):
        with open(DATA_DIR / 'student_data.pkl', 'rb') as f:
            students = pickle.load(f)
    else:
        students = []
    if stu_id and any(s['stu_id'] == stu_id for s in students):
        raise ValueError("รหัสนักศึกษานี้มีอยู่แล้ว")

    video = cv2.VideoCapture(0)
    try:
        if not video.isOpened():
            raise RuntimeError("ไม่สามารถเปิดกล้องได้")

        facedetect = cv2.CascadeClassifier(str(FACE_DETECTOR_PATH))
        if facedetect.empty():
            raise RuntimeError("ไม่พบไฟล์ haarcascade_frontalface_default.xml")
        faces_data = collect_faces(video, facedetect, cv2)
    finally:
        video.release()
        cv2.destroyAllWindows()

    if len(faces_data) != 100:
        raise ValueError("เก็บภาพไม่ครบ 100 ภาพ กรุณาลองใหม่")

    faces_data = np.asarray(faces_data)
    faces_data = faces_data.reshape(100, -1)

    # ======================
    # SAVE FACES
    # ======================
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR)

    if os.path.exists(DATA_DIR / 'faces_data.pkl'):
        with open(DATA_DIR / 'faces_data.pkl', 'rb') as f:
            faces = pickle.load(f)
        faces = np.append(faces, faces_data, axis=0)
    else:
        faces = faces_data

    with open(DATA_DIR / 'faces_data.pkl', 'wb') as f:
        pickle.dump(faces, f)

    # ======================
    # SAVE NAMES
    # ======================
    if os.path.exists(DATA_DIR / 'names.pkl'):
        with open(DATA_DIR / 'names.pkl', 'rb') as f:
            names = pickle.load(f)
        names = names + [name] * 100
    else:
        names = [name] * 100

    with open(DATA_DIR / 'names.pkl', 'wb') as f:
        pickle.dump(names, f)

    # ======================
    # SAVE STUDENT DATA
    # ======================
    student_data = {'stu_id': stu_id, 'name': name}

    # Unknown ที่ไม่มีรหัสเป็นตัวอย่างใบหน้า ไม่เพิ่มเป็นนักศึกษาในรายชื่อเช็คชื่อ
    if name == "Unknown" and not stu_id:
        return
    students.append(student_data)

    with open(DATA_DIR / 'student_data.pkl', 'wb') as f:
        pickle.dump(students, f)


def collect_faces(video, facedetect, cv2):
    faces_data = []
    i = 0
    cv2.namedWindow("Capturing Face", cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.resizeWindow("Capturing Face", 640, 480)
    while True:
        ret, frame = video.read()
        if not ret:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = facedetect.detectMultiScale(gray, 1.3, 5)
        for (x, y, w, h) in faces:
            crop_img = frame[y:y+h, x:x+w]
            resized_img = cv2.resize(crop_img, (50, 50))
            if len(faces_data) < 100 and i % 10 == 0:
                faces_data.append(resized_img)
            i += 1
            cv2.putText(frame, f"Collected: {len(faces_data)}/100", (50, 50),
                        cv2.FONT_HERSHEY_COMPLEX, 1, (50, 50, 255), 1)
            cv2.rectangle(frame, (x, y), (x+w, y+h), (50, 50, 255), 1)
        cv2.imshow("Capturing Face", frame)
        k = cv2.waitKey(1)
        if k == ord('q') or len(faces_data) == 100:
            break
    return faces_data


# ==============================
# VALIDATE FUNCTION
# ==============================
def validate_and_start():
    name = name_entry.get().strip()
    stu_id = stu_id_entry.get().strip()
    if name.casefold() == "unknown":
        name = "Unknown"

    if name == "":
        error_label.config(text="กรุณากรอกชื่อ-นามสกุล", foreground="red")
        return

    if stu_id == "" and name != "Unknown":
        error_label.config(text="กรุณากรอกรหัสนักศึกษา", foreground="red")
        return

    error_label.config(text="")
    start_face_capture(name, stu_id)


# ==============================
# UI
# ==============================
def main():
    global window, name_entry, stu_id_entry, error_label
    window = tk.Tk()
    window.title("ลงทะเบียนนักศึกษา")
    apply_theme(window)
    window_size(window, 650, 660, (590, 620))
    main_frame = ResponsivePanel(window, padding=32)
    main_frame.pack(fill="both", expand=True)
    page_header(main_frame, "บันทึกและจดจำใบหน้า", "กรอกข้อมูลนักศึกษา แล้วอ่านคำขอความยินยอมก่อนเปิดกล้อง")
    card = ttk.Frame(main_frame, style="Card.TFrame", padding=24)
    card.pack(fill="x")
    ttk.Label(card, text="ข้อมูลนักศึกษา", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 20))
    ttk.Label(card, text="ชื่อ-นามสกุล", style="Card.TLabel").pack(anchor="w")
    name_entry = ttk.Entry(card)
    name_entry.pack(fill="x", pady=(6, 18))
    ttk.Label(card, text="รหัสนักศึกษา", style="Card.TLabel").pack(anchor="w")
    stu_id_entry = ttk.Entry(card)
    stu_id_entry.pack(fill="x", pady=(6, 8))
    ttk.Label(card, text="หากชื่อ Unknown สามารถเว้นรหัสนักศึกษาได้", style="CardNote.TLabel").pack(anchor="w")
    error_label = ttk.Label(main_frame, text="", foreground="#B43E46", wraplength=560)
    error_label.pack(fill="x", pady=16)
    ttk.Button(main_frame, text="ถัดไป · อ่านและยืนยันความยินยอม", style="Primary.TButton",
               command=validate_and_start).pack(fill="x")
    ttk.Label(main_frame, text="เมื่อบันทึกเสร็จ สามารถลงทะเบียนคนถัดไปได้ทันที", style="Subtitle.TLabel").pack(anchor="w", pady=(14, 0))
    name_entry.focus_set()
    name_entry.bind("<Return>", lambda event: stu_id_entry.focus_set())
    stu_id_entry.bind("<Return>", lambda event: validate_and_start())

    wrap_labels(main_frame)
    window.mainloop()


if __name__ == "__main__":
    main()
