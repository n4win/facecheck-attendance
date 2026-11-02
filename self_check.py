"""ตรวจตัวแพ็กบนเครื่อง build โดยไม่ใช้กล้องและไม่แตะข้อมูลจริง: menu.py --self-check รายงาน.txt"""
import json
import os
import pickle
import subprocess
import sys
import time
import traceback

TOOL_WAIT_SECONDS = 12


def check_files():
    from app_paths import ABSENCE_SCRIPT_PATH, FACE_DETECTOR_PATH, MODEL_PATH
    import teacher_report
    json.loads(teacher_report.TERMS_PATH.read_text(encoding="utf-8"))
    teacher_report.load_template()
    if "setupAttendanceAutomation" not in ABSENCE_SCRIPT_PATH.read_text(encoding="utf-8"):
        raise RuntimeError("ไม่พบโค้ดระบบสรุปขาดเรียน")
    import cv2
    if cv2.CascadeClassifier(str(FACE_DETECTOR_PATH)).empty():
        raise RuntimeError(f"โหลดตัวตรวจจับใบหน้าไม่ได้: {FACE_DETECTOR_PATH}")
    if not MODEL_PATH.is_file():
        raise RuntimeError(f"ไม่พบโมเดล: {MODEL_PATH}")


def check_google_modules():
    import gspread
    import keyring
    from keyring.backends import fail
    from google_auth_oauthlib.flow import InstalledAppFlow
    from oauth2client.service_account import ServiceAccountCredentials
    from attendance_sessions import THAILAND
    # Linux บนเครื่อง build ไม่มี Secret Service แต่ Windows และ macOS ต้องมีเสมอ
    if sys.platform in ("win32", "darwin") and isinstance(keyring.get_keyring(), fail.Keyring):
        raise RuntimeError("ไม่พบ keychain ของระบบในตัวแพ็ก")
    return gspread.__version__, InstalledAppFlow.__name__, ServiceAccountCredentials.__name__, str(THAILAND)


class MemorySheet:
    def __init__(self):
        self.rows = []

    def get_all_values(self):
        return [list(row) for row in self.rows]

    def update(self, range_name, values, value_input_option=None):
        self.rows[:1] = values

    def append_row(self, values, value_input_option=None):
        self.rows.append(values)


def check_attendance_flow():
    from app_paths import DATA_DIR
    import numpy as np
    import scanstu as scan
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    faces = np.random.default_rng(1).integers(0, 255, (10, 7500), dtype=np.uint8)
    samples = (("faces_data.pkl", faces), ("names.pkl", ["A"] * 5 + ["B"] * 5),
               ("student_data.pkl", [{"stu_id": "001", "name": "A"}, {"stu_id": "002", "name": "B"}]))
    for name, value in samples:
        with (DATA_DIR / name).open("wb") as handle:
            pickle.dump(value, handle)
    app = scan.FaceAttendanceApp.__new__(scan.FaceAttendanceApp)
    sheet = MemorySheet()
    app.sheets, app.similarity_threshold = scan.ScanSheets(sheet), 0.40
    _, students, matcher = app.prepare_session("14-09-2026")
    matcher.match(faces[0].reshape(50, 50, 3))
    app.sheets.save_once(dict(zip(scan.HEADERS, ["14-09-2026", "A", students["A"], "08:00:00", "ตรงเวลา", "ไม่มีหมายเหตุ"])))
    if len(scan.ScanSheets(sheet).today("14-09-2026")) != 1:
        raise RuntimeError("อ่านผลเช็คชื่อกลับมาไม่ได้")


def check_tools(names, tool_command):
    for name in names:
        process = subprocess.Popen(tool_command(name))
        try:
            time.sleep(TOOL_WAIT_SECONDS)
            if process.poll() is not None:
                raise RuntimeError(f"หน้าต่าง {name} ปิดเองด้วยรหัส {process.returncode}")
        finally:
            process.kill()
            process.wait()


def check_preview_and_capture_window():
    # หน้าลงทะเบียนเปิดหน้าต่าง OpenCV ขณะมี Tk อยู่ในโปรเซสเดียวกัน บาง OS อาจพังตรงนี้
    import tkinter as tk
    import cv2
    import numpy as np
    from PIL import Image, ImageTk
    root = tk.Tk()
    root.withdraw()
    ImageTk.PhotoImage(Image.new("RGB", (4, 4)))
    cv2.namedWindow("self-check", cv2.WINDOW_NORMAL | cv2.WINDOW_KEEPRATIO)
    cv2.imshow("self-check", np.zeros((50, 50, 3), dtype=np.uint8))
    cv2.waitKey(1)
    cv2.destroyAllWindows()
    root.destroy()


def run(report_path, tool_names, tool_command):
    if "FACECHECK_DATA_DIR" not in os.environ:
        print("ต้องตั้ง FACECHECK_DATA_DIR เป็นโฟลเดอร์ชั่วคราวก่อน เพื่อไม่ให้แตะข้อมูลจริง", file=sys.stderr)
        return 2
    steps = (("files", check_files), ("google modules", check_google_modules),
             ("attendance flow", check_attendance_flow),
             ("tool windows", lambda: check_tools(tool_names, tool_command)),
             ("preview and capture window", check_preview_and_capture_window))
    failed = False
    with open(report_path, "w", encoding="utf-8") as report:
        for name, step in steps:
            # เขียนก่อนเริ่ม เพื่อให้รู้ขั้นที่พังถ้าโปรเซสล้มกลางทาง
            report.write(f"START {name}\n")
            report.flush()
            try:
                step()
                report.write(f"OK {name}\n")
            except Exception:
                failed = True
                report.write(f"FAIL {name}\n{traceback.format_exc()}\n")
            report.flush()
        report.write("RESULT " + ("FAIL" if failed else "PASS") + "\n")
    return 1 if failed else 0
