"""เลือกวันที่ ตั้งเวลา และเช็คชื่อด้วยใบหน้า พร้อมตารางสถานะและ Google Sheets."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
import json
import pickle
import uuid
import tkinter as tk
from tkinter import messagebox, ttk
from ui_theme import fit_image_size, ResponsivePanel, responsive_row, wrap_labels, table_scrollbars, apply_theme, page_header, window_size, status_table

from app_paths import DATA_DIR, FACE_DETECTOR_PATH
from attendance_sheets import AttendanceSheets, HEADERS, valid_headers
import google_settings
from face_similarity import FaceMatcher, StableMatch, DEFAULT_THRESHOLD, REQUIRED_FRAMES

SETTINGS = DATA_DIR / "attendance_time.json"
OUTBOX = DATA_DIR / "face_attendance_pending.json"
STATUSES = {"ตรงเวลา": "ตรงเวลา", "มา": "ตรงเวลา", "On time": "ตรงเวลา", "มาสาย": "มาสาย", "Late": "มาสาย"}
DISPLAY_STATUSES = {**STATUSES, "ขาดเรียน": "ขาดเรียน"}


def parse_attendance_date(value):
    value = value.strip()
    try:
        if len(value) != 10 or value[4] != "-" or value[7] != "-":
            raise ValueError
        return datetime.strptime(value, "%Y-%m-%d").strftime("%d-%m-%Y")
    except ValueError:
        raise ValueError("กรุณาระบุวันที่ที่มีจริง รูปแบบ YYYY-MM-DD (ค.ศ.) เช่น 2026-09-29") from None


def parse_cutoff(value):
    value = value.strip()
    if len(value) != 5 or value[2] != ":" or not (value[:2] + value[3:]).isdigit():
        raise ValueError("กรุณาระบุเวลาแบบ HH:MM เช่น 08:30")
    try:
        return datetime.strptime(value, "%H:%M").time()
    except ValueError:
        raise ValueError("เวลาไม่ถูกต้อง ใช้เวลา 00:00 ถึง 23:59") from None


def attendance_status(now, cutoff):
    return "ตรงเวลา" if (now.hour, now.minute) <= (cutoff.hour, cutoff.minute) else "มาสาย"


def time_description(cutoff):
    if (cutoff.hour, cutoff.minute) == (23, 59):
        return "ตรงเวลาตลอดวัน (ไม่มีช่วงมาสายในวันนั้น)"
    late = (datetime.combine(datetime.today(), cutoff) + timedelta(minutes=1)).strftime("%H:%M")
    return f"ตรงเวลาถึง {cutoff:%H:%M}:59 • มาสายตั้งแต่ {late}:00 เป็นต้นไป"


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def row_key(row):
    return row["DATE"], row["STUDENT_ID"]


def is_unknown(name):
    return name.strip().casefold() == "unknown"


class ScanSheets(AttendanceSheets):
    def records(self):
        sheet = self.connect()
        values = sheet.get_all_values()
        if not values:
            sheet.update(range_name="A1:F1", values=[HEADERS], value_input_option="RAW")
            return []
        if not valid_headers(values[0]):
            raise ValueError("หัวคอลัมน์ในชีตไม่ตรงกับข้อมูลการเช็คชื่อ")
        return [(index, dict(zip(HEADERS, (row + [""] * 6)[:6])))
                for index, row in enumerate(values[1:], 2)]

    def today(self, day):
        return [row for _, row in self.records() if row["DATE"] == day
                and not is_unknown(row["NAME"]) and row["STATUS"] in DISPLAY_STATUSES]

    def save_once(self, record):
        if is_unknown(record["NAME"]):
            raise ValueError("ไม่บันทึกการมาเรียนของ Unknown")
        matches = [(index, row) for index, row in self.records() if row_key(row) == row_key(record)]
        if len(matches) > 1:
            raise ValueError("พบรหัสและวันที่ซ้ำในชีต กรุณาตรวจสอบก่อนส่งอีกครั้ง")
        if matches and matches[0][1]["STATUS"] in STATUSES:
            return matches[0][1]
        values = [record[key] for key in HEADERS]
        if matches:
            index = matches[0][0]
            self.connect().update(range_name=f"A{index}:F{index}", values=[values], value_input_option="RAW")
        else:
            self.connect().append_row(values, value_input_option="RAW")
        return record


class FaceAttendanceApp:
    def __init__(self, root):
        self.root, self.video = root, None
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.sheets, self.jobs = ScanSheets(), []
        self.saved, self.pending, self.errors, self.sending = {}, {}, {}, set()
        self.annotation = None
        self.annotation_key = None
        self.frame_id = None
        self.closed = False
        self.round_id = None
        root.title("เลือกวันที่และเวลาเช็คชื่อ")
        apply_theme(root)
        window_size(root, 730, 700, (650, 650))
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.setup = ResponsivePanel(root, padding=32)
        self.setup.pack(fill="both", expand=True)
        page_header(self.setup, "ตั้งค่าการเช็คชื่อ", "เลือกวันที่และกำหนดเวลา แล้วเริ่มเช็คชื่อผ่านกล้อง")
        fields = ttk.Frame(self.setup)
        fields.pack(fill="x")
        date_field = ttk.Frame(fields)
        date_field.pack(side="left", anchor="n", padx=(0, 28))
        ttk.Label(date_field, text="วันที่เช็คชื่อ (ค.ศ.)", style="Section.TLabel").pack(anchor="w")
        date_row = ttk.Frame(date_field)
        date_row.pack(anchor="w", pady=(10, 6))
        self.date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
        self.date_entry = ttk.Entry(date_row, textvariable=self.date_var, width=13)
        self.date_entry.pack(side="left")
        self.today_button = ttk.Button(date_row, text="วันนี้", command=lambda: self.date_var.set(datetime.now().strftime("%Y-%m-%d")))
        self.today_button.pack(side="left", padx=(6, 0))
        ttk.Label(date_field, text="ปี-เดือน-วัน เช่น 2026-09-29", style="Subtitle.TLabel").pack(anchor="w")
        time_field = ttk.Frame(fields)
        time_field.pack(side="left", anchor="n")
        ttk.Label(time_field, text="ตรงเวลาได้ถึง", style="Section.TLabel").pack(anchor="w")
        initial = "08:30"
        try:
            settings = json.loads(SETTINGS.read_text(encoding="utf-8"))
            initial = settings["on_time_until"]
            parse_cutoff(initial)
        except (OSError, ValueError, KeyError, TypeError, AttributeError):
            initial = "08:30"
        self.cutoff_var = tk.StringVar(value=initial)
        ttk.Entry(time_field, textvariable=self.cutoff_var, width=9).pack(anchor="w", pady=(10, 6))
        ttk.Label(time_field, text="เวลา 24 ชั่วโมง เช่น 08:30", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 16))
        end_initial = "17:00"
        try:
            end_initial = json.loads(SETTINGS.read_text(encoding="utf-8")).get("class_end_time", "17:00")
            parse_cutoff(end_initial)
        except (OSError, ValueError, TypeError, AttributeError):
            end_initial = "17:00"
        ttk.Label(self.setup, text="เวลาเลิกเรียน (เวลาไทย)", style="Section.TLabel").pack(anchor="w")
        self.end_time_var = tk.StringVar(value=end_initial)
        ttk.Entry(self.setup, textvariable=self.end_time_var, width=9).pack(anchor="w", pady=(6, 6))
        ttk.Label(self.setup, text="หลังเวลาเลิกเรียน Google ตรวจทุกประมาณ 15 นาที แล้วเพิ่มผู้ที่ยังไม่เช็คชื่อเป็นขาดเรียน" if google_settings.absence_summary_enabled()
                  else "ใช้เวลาเลิกเรียนเมื่อติดตั้งระบบสรุปขาดเรียนในชีตแล้ว ตอนนี้ยังไม่สรุปขาดเรียนอัตโนมัติ",
                  style="Subtitle.TLabel", wraplength=570).pack(anchor="w", pady=(0, 12))
        self.preview = tk.StringVar()
        ttk.Label(self.setup, textvariable=self.preview, style="Summary.TLabel", wraplength=560).pack(fill="x")
        ttk.Label(self.setup, text=f"คะแนนความใกล้เคียงขั้นต่ำ {DEFAULT_THRESHOLD:.2f} (cosine)\nต้องผ่านต่อเนื่องอย่างน้อย 5 เฟรม และ 0.8 วินาที · เช็คทีละคน",
                  style="Subtitle.TLabel", wraplength=620).pack(anchor="w", pady=(6, 0))
        self.notice = tk.StringVar(value="บันทึกตามวันที่ที่เลือก โดยใช้เวลาขณะสแกนตัดสินตรงเวลา/มาสาย")
        ttk.Label(self.setup, textvariable=self.notice, style="Subtitle.TLabel", wraplength=570).pack(anchor="w", pady=16)
        self.start_button = ttk.Button(self.setup, text="เริ่มเช็คชื่อผ่านกล้อง", command=self.start, style="Primary.TButton")
        self.start_button.pack(fill="x")
        self.cutoff_var.trace_add("write", lambda *_: self.update_preview())
        responsive_row(fields, minimum=280)
        self.date_entry.pack_configure(fill="x", expand=True)
        wrap_labels(self.setup)
        self.update_preview()
        self.poll_id = root.after(100, self.poll_jobs)

    def update_preview(self):
        try:
            self.preview.set(time_description(parse_cutoff(self.cutoff_var.get())))
        except ValueError as exc:
            self.preview.set(str(exc))

    def submit(self, function, success, failure, *args):
        self.jobs.append((self.executor.submit(function, *args), success, failure))

    def poll_jobs(self):
        for job in list(self.jobs):
            future, success, failure = job
            if future.done():
                self.jobs.remove(job)
                try:
                    value = future.result()
                    success(value)
                except Exception as exc:
                    failure(exc)
        if not self.closed:
            self.poll_id = self.root.after(100, self.poll_jobs)

    def start(self):
        try:
            self.session_day = parse_attendance_date(self.date_var.get())
            self.cutoff = parse_cutoff(self.cutoff_var.get())
            self.end_time = parse_cutoff(self.end_time_var.get())
            if self.end_time <= self.cutoff:
                raise ValueError("เวลาเลิกเรียนต้องอยู่หลังเวลาตรงเวลาได้ถึง")
            self.similarity_threshold = DEFAULT_THRESHOLD
            write_json(SETTINGS, {"on_time_until": self.cutoff.strftime("%H:%M"), "similarity_threshold": self.similarity_threshold, "class_end_time": self.end_time.strftime("%H:%M")})
            if OUTBOX.exists():
                pending = json.loads(OUTBOX.read_text(encoding="utf-8"))
                if not isinstance(pending, list) or any(
                    not isinstance(row, dict) or any(not isinstance(row.get(key), str) for key in HEADERS)
                    or row["STATUS"] not in STATUSES for row in pending
                ):
                    raise ValueError("ไฟล์รายการรอส่งไม่ถูกต้อง กรุณาตรวจสอบก่อนเริ่ม")
                self.pending = {row_key(row): row for row in pending if not is_unknown(row["NAME"])}
                self.errors = {key: "รอส่งอีกครั้ง" for key in self.pending}
        except (ValueError, OSError) as exc:
            messagebox.showerror("เริ่มเช็คชื่อไม่ได้", str(exc), parent=self.root)
            return
        self.start_button.configure(state="disabled")
        self.date_entry.configure(state="disabled")
        self.today_button.configure(state="disabled")
        self.round_id = uuid.uuid4().hex
        self.notice.set("กำลังโหลดข้อมูลและเตรียม SFace ในเครื่อง อาจใช้เวลาสักครู่…")
        self.submit(self.prepare_session, self.open_camera, self.start_failed, self.session_day)

    def prepare_session(self, day):
        """เตรียมโมเดลใน background เพื่อให้หน้าต่างยังตอบสนอง."""
        rows = self.sheets.today(day)
        if not all((DATA_DIR / name).exists() for name in ("names.pkl", "faces_data.pkl", "student_data.pkl")):
            raise ValueError("ยังไม่มีข้อมูลใบหน้า กรุณาลงทะเบียนนักศึกษาก่อน")
        with (DATA_DIR / "names.pkl").open("rb") as handle:
            labels = pickle.load(handle)
        with (DATA_DIR / "faces_data.pkl").open("rb") as handle:
            faces = pickle.load(handle)
        with (DATA_DIR / "student_data.pkl").open("rb") as handle:
            records = pickle.load(handle)
        students = {}
        registered = set(labels)
        for row in records:
            if not is_unknown(row["name"]) and row["name"] in registered and str(row["stu_id"]).strip():
                if row["name"] in students:
                    raise ValueError("มีนักศึกษาชื่อซ้ำ กรุณาตรวจสอบรายชื่อก่อนเช็คชื่อ")
                students[row["name"]] = str(row["stu_id"])
        matcher = FaceMatcher(faces, labels, self.similarity_threshold)
        return rows, students, matcher

    def start_failed(self, exc):
        self.notice.set(f"เริ่มเช็คชื่อไม่ได้: {exc}")
        self.start_button.configure(state="normal")
        self.date_entry.configure(state="normal")
        self.today_button.configure(state="normal")

    def open_camera(self, prepared):
        try:
            import cv2
            from PIL import Image, ImageTk
            self.cv2, self.Image, self.ImageTk = cv2, Image, ImageTk
            rows, self.students, self.matcher = prepared
            self.stability = StableMatch()
            self.detector = cv2.CascadeClassifier(str(FACE_DETECTOR_PATH))
            if self.detector.empty():
                raise ValueError("ไม่พบตัวตรวจจับใบหน้า")
            self.video = cv2.VideoCapture(0)
            if not self.video.isOpened():
                raise RuntimeError("ไม่สามารถเปิดกล้องได้")
            self.video.set(cv2.CAP_PROP_FRAME_WIDTH, 480)
            self.video.set(cv2.CAP_PROP_FRAME_HEIGHT, 360)
        except Exception as exc:
            if self.video is not None:
                self.video.release()
                self.video = None
            self.start_failed(exc)
            return
        # Register only after the camera has opened successfully. Do not scan until
        # Google has the complete roster, including when nobody attends this round.
        self.notice.set("กำลังเปิดรอบบน Google เพื่อสรุปขาดเรียนหลังเวลาเลิกเรียน…" if google_settings.absence_summary_enabled() else "กำลังเตรียมการเช็คชื่อ…")
        self.submit(self.sheets.open_session, lambda _: self.begin_scanning(rows),
                    self.round_failed, self.round_id, self.session_day,
                    [{"name": name, "student_id": sid} for name, sid in self.students.items()], self.end_time.strftime("%H:%M"))

    def round_failed(self, exc):
        if self.video is not None:
            self.video.release()
            self.video = None
        self.start_failed(exc)

    def begin_scanning(self, rows):
        self.setup.shell.destroy()
        self.build_scan_window()
        self.merge_records(rows)
        self.retry()
        self.update_frame()

    def build_scan_window(self):
        self.root.title("เช็คชื่อด้วยใบหน้า")
        window_size(self.root, 1240, 800, (1140, 680))
        panel = ResponsivePanel(self.root, padding=24)
        panel.pack(fill="both", expand=True)
        page_header(panel, "เช็คชื่อผ่านกล้อง", f"วันที่เช็คชื่อ {self.session_day} • เลิกเรียน {self.end_time:%H:%M} • " + time_description(self.cutoff) + f"\nคะแนนขั้นต่ำ {self.similarity_threshold:.2f} · ยืนยันใบหน้าทีละคนก่อนบันทึก")
        columns = ttk.Frame(panel)
        columns.pack(fill="both", expand=True)
        left = ttk.Frame(columns, style="Card.TFrame", padding=12)
        left.pack(side="left", fill="both", expand=True)
        ttk.Label(left, text="ภาพจากกล้อง", style="CardTitle.TLabel").pack(anchor="w", pady=(0, 12))
        self.video_area = ttk.Frame(left, height=300, width=1)
        self.video_area.pack(fill="both", expand=True)
        self.video_area.pack_propagate(False)
        self.video_label = ttk.Label(self.video_area, background="#172B3A", anchor="center")
        self.video_label.pack(fill="both", expand=True)
        self.detected = tk.StringVar(value="รอตรวจพบใบหน้า…")
        ttk.Label(left, textvariable=self.detected, style="CardNote.TLabel", wraplength=440).pack(anchor="w", pady=14)
        right = ttk.Frame(columns)
        right.pack(side="left", fill="both", expand=True)
        self.summary = tk.StringVar()
        ttk.Label(right, textvariable=self.summary, style="Summary.TLabel").pack(fill="x", pady=(0, 12))
        table = ttk.Frame(right)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("id", "name", "time", "status", "sync"), show="headings")
        for key, title, width in (("id", "รหัส", 80), ("name", "ชื่อ-นามสกุล", 170), ("time", "เวลา", 75), ("status", "สถานะ", 75), ("sync", "Google Sheets", 110)):
            self.tree.heading(key, text=title)
            self.tree.column(key, width=width, minwidth=60)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        status_table(self.tree)
        buttons = ttk.Frame(panel)
        buttons.pack(fill="x", pady=12)
        ttk.Button(buttons, text="หยุดเช็คชื่อ", command=self.close, style="Danger.TButton").pack(side="right")
        ttk.Label(panel, textvariable=self.notice, style="Subtitle.TLabel", wraplength=1100).pack(anchor="w")
        responsive_row(columns, minimum=470)
        table_scrollbars(table, self.tree)
        wrap_labels(panel)
        self.notice.set(f"เปิดรอบวันที่ {self.session_day} แล้ว • Google จะสรุปขาดเรียนหลัง {self.end_time:%H:%M} (ตรวจทุกประมาณ 15 นาที)" if google_settings.absence_summary_enabled()
                        else f"เปิดรอบวันที่ {self.session_day} แล้ว • ไม่มีการสรุปขาดเรียนอัตโนมัติ")

    def merge_records(self, rows):
        for row in rows:
            self.saved[row_key(row)] = row
        self.render_table()

    def render_table(self):
        day = self.session_day
        self.tree.delete(*self.tree.get_children())
        counts = {"ตรงเวลา": 0, "มาสาย": 0, "ขาดเรียน": 0}
        for key, row in {**self.saved, **self.pending}.items():
            if key[0] != day or is_unknown(row["NAME"]):
                continue
            status = DISPLAY_STATUSES[row["STATUS"]]
            sync = "ส่งไม่สำเร็จ" if key in self.errors else "กำลังส่ง" if key in self.pending else "บันทึกแล้ว"
            if sync == "บันทึกแล้ว":
                counts[status] += 1
            self.tree.insert("", "end", values=(row["STUDENT_ID"], row["NAME"], row["TIME"], status, sync), tags=(status,))
        self.summary.set(f"วันที่ {day} • ตรงเวลา {counts['ตรงเวลา']} • มาสาย {counts['มาสาย']} • ขาด {counts['ขาดเรียน']}")

    def send_record(self, row):
        if is_unknown(row["NAME"]):
            return
        key = row_key(row)
        if key in self.sending:
            return
        # บันทึกรายการรอส่งก่อนเรียกเครือข่าย เพื่อส่งต่อได้เมื่อเปิดโปรแกรมใหม่
        pending = {**self.pending, key: row}
        try:
            write_json(OUTBOX, list(pending.values()))
        except OSError as exc:
            self.notice.set(f"บันทึกรายการรอส่งไม่ได้: {exc}")
            return
        self.pending = pending
        self.errors.pop(key, None)
        self.sending.add(key)
        self.render_table()
        def done(saved):
            remaining = {k: value for k, value in self.pending.items() if k != key}
            write_json(OUTBOX, list(remaining.values()))
            self.pending = remaining
            self.saved[key] = saved
            self.sending.discard(key)
            self.errors.pop(key, None)
            self.notice.set(f"บันทึกแล้ว: {saved['NAME']} — {STATUSES[saved['STATUS']]}")
            self.render_table()
        def failed(exc):
            self.sending.discard(key)
            self.errors[key] = str(exc)
            self.notice.set(f"ส่ง {row['NAME']} ไม่สำเร็จ เก็บรายการไว้แล้ว จะลองส่งเมื่อเริ่มเช็คชื่อครั้งถัดไป: {exc}")
            self.render_table()
        self.submit(self.sheets.save_once, done, failed, row)

    def retry(self):
        for key in list(self.errors):
            self.send_record(self.pending[key])

    def ask_annotation(self, row):
        self.annotation_key = row_key(row)
        dialog = tk.Toplevel(self.root)
        self.annotation = dialog
        dialog.title(f"หมายเหตุการมาสาย — {row['NAME']}")
        apply_theme(dialog)
        window_size(dialog, 480, 530, (420, 470))
        dialog.transient(self.root)
        panel = ResponsivePanel(dialog, padding=28)
        panel.pack(fill="both", expand=True)
        page_header(panel, "หมายเหตุการมาสาย", row["NAME"])
        ttk.Label(panel, text="เลือกเหตุผลได้มากกว่า 1 ข้อ", style="Subtitle.TLabel").pack(anchor="w", pady=(0, 10))
        reasons = {}
        for text in ("รถติด", "เหตุสุดวิสัย", "ตื่นสาย", "อุบัติเหตุ", "อื่นๆ"):
            reasons[text] = tk.BooleanVar(value=False)
            ttk.Checkbutton(panel, text=text, variable=reasons[text]).pack(anchor="w", pady=3)
        def save():
            row["ANNOTATION"] = ", ".join(text for text, var in reasons.items() if var.get()) or "ไม่มีหมายเหตุ"
            self.send_record(row)
            if row_key(row) in self.pending:
                self.annotation_key = None
                self.annotation = None
                dialog.destroy()
        ttk.Button(panel, text="บันทึกการเช็คชื่อ", command=save, style="Primary.TButton").pack(fill="x", pady=(18, 0))
        wrap_labels(panel)
        dialog.protocol("WM_DELETE_WINDOW", save)

    def update_frame(self):
        if self.closed:
            return
        try:
            ok, frame = self.video.read()
            if not ok:
                self.stability.reset()
                self.detected.set("อ่านภาพจากกล้องไม่ได้ กรุณาตรวจสอบกล้อง")
            else:
                cv2 = self.cv2
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                faces = self.detector.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))
                if len(faces) != 1:
                    self.stability.reset()
                descriptions = []
                for x, y, w, h in faces:
                    crop = frame[y:y+h, x:x+w]
                    match = self.matcher.match(crop)
                    name = match.name
                    sharpness = cv2.Laplacian(cv2.cvtColor(cv2.resize(crop, (112, 112)), cv2.COLOR_BGR2GRAY), cv2.CV_64F).var()
                    good_image = min(w, h) >= 80 and sharpness >= 35
                    accepted = match.accepted and good_image and len(faces) == 1 and name in self.students
                    confirmed = self.stability.observe(name, accepted, (x, y, w, h)) if len(faces) == 1 else False
                    now = datetime.now()
                    student_id = self.students.get(name)
                    key = (self.session_day, student_id)
                    known = accepted and confirmed and student_id is not None and not is_unknown(name)
                    present = key in self.saved and self.saved[key]["STATUS"] in STATUSES
                    if known and not present and key not in self.pending and key != self.annotation_key:
                        row = dict(zip(HEADERS, [key[0], name, student_id, now.strftime("%H:%M:%S"), attendance_status(now, self.cutoff), "ไม่มีหมายเหตุ"]))
                        if row["STATUS"] == "มาสาย":
                            if self.annotation is None:
                                self.ask_annotation(row)
                        else:
                            self.send_record(row)
                    if present:
                        description = f"{name} — บันทึกแล้ว ({STATUSES[self.saved[key]['STATUS']]})"
                    elif key in self.errors:
                        description = f"{name} — ส่งไม่สำเร็จ"
                    elif key in self.pending:
                        description = f"{name} — กำลังส่ง"
                    else:
                        if len(faces) > 1:
                            reason = "กรุณาเข้ากล้องทีละคน — ยังไม่บันทึก"
                        elif not good_image:
                            reason = "ขยับเข้าใกล้กล้องและให้ภาพชัด — ยังไม่บันทึก"
                        elif accepted and not confirmed:
                            reason = f"กำลังยืนยัน {min(self.stability.count, REQUIRED_FRAMES)}/{REQUIRED_FRAMES} เฟรม"
                        else:
                            reason = match.reason if not known else "รอเช็คชื่อ"
                        description = f"{name} — {reason}"
                    description += f"\nคะแนนความใกล้เคียง {match.score:.3f} / เกณฑ์ {self.similarity_threshold:.2f}"
                    descriptions.append(description)
                    cv2.rectangle(frame, (x, y), (x+w, y+h), (0, 180, 0) if present else (0, 160, 255) if known else (0, 0, 255), 2)
                self.detected.set("\n".join(descriptions) or "รอตรวจพบใบหน้า…")
                image = self.Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                area = getattr(self, "video_area", None)
                if area is None:
                    image.thumbnail((480, 360))
                else:
                    size = (max(1, area.winfo_width()), max(1, area.winfo_height()))
                    image = image.resize(fit_image_size(image.size, size))
                photo = self.ImageTk.PhotoImage(image=image)
                self.video_label.configure(image=photo)
                self.video_label.image = photo
        except Exception as exc:
            self.stability.reset()
            self.notice.set(f"ประมวลผลภาพไม่สำเร็จ: {exc}")
        self.frame_id = self.root.after(60, self.update_frame)

    def close(self):
        if self.annotation is not None:
            messagebox.showwarning("ยังไม่ได้บันทึกหมายเหตุ", "กรุณาบันทึกหมายเหตุก่อนปิดโปรแกรม", parent=self.root)
            return
        if self.pending and not messagebox.askyesno("ยังมีรายการรอส่ง", "ยังมีรายการรอส่ง Google Sheets ต้องการปิดหรือไม่?\nรายการจะเก็บในเครื่องและส่งอีกครั้งเมื่อเริ่มเช็คชื่อครั้งถัดไป", parent=self.root):
            return
        self.closed = True
        self.root.after_cancel(self.poll_id)
        if self.frame_id is not None:
            self.root.after_cancel(self.frame_id)
        if self.video is not None:
            self.video.release()
        self.executor.shutdown(wait=False, cancel_futures=True)
        self.root.destroy()


def main():
    root = tk.Tk()
    FaceAttendanceApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
