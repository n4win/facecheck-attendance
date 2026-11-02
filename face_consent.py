"""Explicit educational face-data consent before camera capture."""
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import tkinter as tk
from tkinter import messagebox, ttk
from tkinter.scrolledtext import ScrolledText
from app_paths import DATA_DIR
from ui_theme import ResponsivePanel, responsive_row, wrap_labels, apply_theme, page_header, window_size, SURFACE, INK, BORDER

POLICY_VERSION = "education-face-v2"
SETTINGS_PATH = DATA_DIR / "face_consent_settings.json"
FIELDS = {
    "controller": "ผู้ควบคุมข้อมูล / สถานศึกษาที่รับผิดชอบ",
    "contact": "ช่องทางติดต่อและขอถอนความยินยอม",
    "retention": "ระยะเวลาเก็บข้อมูลและกำหนดลบ (รวมหลักฐานความยินยอม)",
    "access": "ผู้มีสิทธิเข้าถึงข้อมูล / ผู้รับข้อมูล",
}


def validate_settings(settings):
    if not isinstance(settings, dict) or any(
        not isinstance(settings.get(key), str) or not settings[key].strip() for key in FIELDS
    ):
        raise ValueError("กรุณาระบุข้อมูลผู้รับผิดชอบ ช่องทางติดต่อ ระยะเวลาเก็บ และผู้เข้าถึงข้อมูลให้ครบ")


def consent_text(settings, name, student_id):
    validate_settings(settings)
    return f"""หนังสือแจ้งการประมวลผลข้อมูลและขอความยินยอมใช้ข้อมูลใบหน้า
สำหรับโครงงานระบบเช็คชื่อด้วยใบหน้าเพื่อการศึกษา

ผู้เข้าร่วม: {name}
รหัสนักศึกษา: {student_id}
ผู้ควบคุมข้อมูลส่วนบุคคล: {settings['controller']}
ติดต่อ / ถอนความยินยอม: {settings['contact']}

1. วัตถุประสงค์
ขอเก็บรวบรวมและใช้ภาพใบหน้าและข้อมูลที่ประมวลผลจากใบหน้าเพื่อการศึกษา ได้แก่ การพัฒนา ทดลอง และประเมินระบบจดจำใบหน้าสำหรับระบุตัวตนและเช็คชื่อในโครงงานนี้เท่านั้น ไม่รวมการโฆษณา การจำหน่ายข้อมูล หรือการนำไปฝึกระบบอื่นนอกวัตถุประสงค์นี้

2. ข้อมูลที่เก็บและวิธีใช้
เมื่อยินยอม ระบบจะเปิดกล้องและเก็บตัวอย่างภาพใบหน้า 100 ตัวอย่าง เชื่อมโยงกับชื่อ-นามสกุลและรหัสนักศึกษา ภาพใบหน้าที่ใช้ระบุตัวบุคคลเป็นข้อมูลชีวภาพที่ได้รับการคุ้มครองเป็นพิเศษ จึงขอความยินยอมโดยชัดแจ้งก่อนเก็บข้อมูล
ข้อมูลใบหน้าจัดเก็บในเครื่องที่ใช้งานโครงงาน และนำไปใช้จดจำใบหน้า เมื่อเช็คชื่อ ระบบบันทึกชื่อ รหัสนักศึกษา วันที่ เวลา สถานะ และหมายเหตุในเครื่อง และหากผู้รับผิดชอบเชื่อมต่อ Google Sheets ของโครงงานไว้ ระบบจะส่งข้อมูลเหล่านี้ไปยัง Google Sheets ด้วย หน้าลงทะเบียนนี้ไม่ส่งภาพใบหน้าไป Google Sheets
ระบบเก็บหลักฐานการยินยอม ได้แก่ ชื่อ รหัส วันเวลา รุ่นและข้อความที่แสดง เพื่อให้ตรวจสอบการให้ความยินยอมได้

3. ผู้เข้าถึงและระยะเวลาเก็บ
ผู้มีสิทธิเข้าถึง / ผู้รับข้อมูล: {settings['access']}
ระยะเวลาเก็บและกำหนดลบ: {settings['retention']}
ผู้ควบคุมข้อมูลเป็นผู้รับผิดชอบจัดการสิทธิ์เข้าถึงและดำเนินการลบตามกำหนด

4. การเลือกและการถอนความยินยอม
การยินยอมเป็นความสมัครใจ สามารถเลือกไม่ยินยอมหรือปิดหน้าต่างนี้ได้ โดยระบบจะไม่เปิดกล้องและไม่เก็บใบหน้าในการลงทะเบียนครั้งนี้ สามารถขอใช้การเช็คชื่อด้วยมือกับผู้รับผิดชอบแทนได้
สามารถถอนความยินยอมผ่านช่องทางติดต่อข้างต้นได้ทุกเมื่อ การถอนความยินยอมไม่กระทบการประมวลผลที่ชอบด้วยกฎหมายก่อนถอน หลังรับคำขอ ผู้รับผิดชอบต้องดำเนินการหยุดใช้ใบหน้าตามความยินยอมและพิจารณาลบข้อมูลตามสิทธิและข้อยกเว้นที่กฎหมายกำหนด โดยใช้วิธีเช็คชื่ออื่นแทน

5. สิทธิของเจ้าของข้อมูล
สามารถติดต่อขอเข้าถึงหรือรับสำเนา แก้ไข ลบ จำกัดการใช้ คัดค้าน หรือขอโอนข้อมูลได้ตามเงื่อนไขของกฎหมาย และร้องเรียนต่อสำนักงานคณะกรรมการคุ้มครองข้อมูลส่วนบุคคลได้
กรณีผู้เยาว์หรือผู้ที่ต้องมีผู้แทนให้ความยินยอม ให้ติดต่อผู้รับผิดชอบเพื่อตรวจสอบและดำเนินการขอความยินยอมจากผู้มีอำนาจตามกฎหมายก่อนลงทะเบียน

การยืนยันด้านล่างเป็นการยินยอมให้เก็บรวบรวมและใช้ข้อมูลใบหน้าเพื่อวัตถุประสงค์ทางการศึกษาที่ระบุข้างต้นเท่านั้น
รุ่นข้อความ: {POLICY_VERSION}
"""


def record_consent(name, student_id, text, path=None):
    path = Path(path) if path is not None else DATA_DIR / "face_consents.sqlite3"
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path)
    try:
        with db:
            db.execute("""CREATE TABLE IF NOT EXISTS consents (
                id INTEGER PRIMARY KEY, student_id TEXT NOT NULL, name TEXT NOT NULL,
                consented_at TEXT NOT NULL, policy_version TEXT NOT NULL,
                notice TEXT NOT NULL, decision TEXT NOT NULL
            )""")
            db.execute("INSERT INTO consents VALUES (NULL, ?, ?, ?, ?, ?, ?)",
                       (student_id, name, datetime.now().astimezone().isoformat(),
                        POLICY_VERSION, text, "explicitly_agreed"))
    finally:
        db.close()


def configure_settings(parent):
    settings = {}
    if SETTINGS_PATH.exists():
        try:
            settings = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            validate_settings(settings)
            return settings
        except (OSError, ValueError):
            if not isinstance(settings, dict):
                settings = {}
    dialog = tk.Toplevel(parent)
    dialog.title("ข้อมูลโครงงาน — สำหรับผู้รับผิดชอบ")
    apply_theme(dialog)
    window_size(dialog, 780, 680, (700, 620))
    dialog.transient(parent)
    panel = ResponsivePanel(dialog, padding=28)
    panel.pack(fill="both", expand=True)
    page_header(panel, "ข้อมูลโครงงาน", "สำหรับผู้รับผิดชอบ · กรอกข้อมูลจริงก่อนขอความยินยอม")
    entries = {}
    for key, label in FIELDS.items():
        ttk.Label(panel, text=label).pack(anchor="w", pady=(12, 6))
        entries[key] = tk.StringVar(value=settings.get(key, ""))
        ttk.Entry(panel, textvariable=entries[key]).pack(fill="x")
    result = None

    def save():
        nonlocal result
        values = {key: var.get().strip() for key, var in entries.items()}
        try:
            validate_settings(values)
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            temporary = SETTINGS_PATH.with_suffix(".tmp")
            temporary.write_text(json.dumps(values, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(SETTINGS_PATH)
        except (OSError, ValueError) as exc:
            messagebox.showerror("บันทึกข้อมูลไม่ได้", str(exc), parent=dialog)
            return
        result = values
        dialog.destroy()

    buttons = ttk.Frame(panel)
    buttons.pack(fill="x", pady=20)
    ttk.Button(buttons, text="ยกเลิก", command=dialog.destroy).pack(side="left")
    ttk.Button(buttons, text="บันทึกและเปิดข้อความขอความยินยอม", command=save, style="Primary.TButton").pack(side="right")
    responsive_row(buttons, minimum=310)
    wrap_labels(panel)
    dialog.grab_set()
    parent.wait_window(dialog)
    return result


def request_face_consent(parent, name, student_id):
    settings = configure_settings(parent)
    if settings is None:
        return False
    notice = consent_text(settings, name, student_id)
    dialog = tk.Toplevel(parent)
    dialog.title("ความยินยอมใช้ข้อมูลใบหน้าเพื่อการศึกษา")
    family = apply_theme(dialog)
    window_size(dialog, 880, 800, (760, 640))
    dialog.transient(parent)
    panel = ResponsivePanel(dialog, padding=28)
    panel.pack(fill="both", expand=True)
    page_header(panel, "ความยินยอมใช้ข้อมูลใบหน้า", "กรุณาอ่านรายละเอียด · กล้องจะเปิดหลังจากคุณยืนยันความยินยอมเท่านั้น")
    body = ScrolledText(panel, wrap="word", font=(family, 12), padx=20, pady=20, height=16,
                        background=SURFACE, foreground=INK, relief="flat", borderwidth=0,
                        highlightthickness=1, highlightbackground=BORDER, spacing1=4, spacing3=5)
    body.pack(fill="both", expand=True)
    body.insert("1.0", notice)
    body.configure(state="disabled")
    agreed = tk.BooleanVar(value=False)
    accepted = False

    def accept():
        nonlocal accepted
        if not agreed.get():
            return
        try:
            record_consent(name, student_id, notice)
        except (OSError, sqlite3.Error) as exc:
            messagebox.showerror("บันทึกความยินยอมไม่ได้", f"ยังไม่เปิดกล้อง กรุณาลองใหม่\n{exc}", parent=dialog)
            return
        accepted = True
        dialog.destroy()

    checkbox = ttk.Checkbutton(panel, variable=agreed,
                              text="ฉันได้อ่านและยินยอมโดยชัดแจ้ง\nให้เก็บและใช้ข้อมูลใบหน้าเพื่อการศึกษา\nตามข้อความข้างต้น",
                              command=lambda: confirm.configure(state="normal" if agreed.get() else "disabled"))
    checkbox.pack(anchor="w", pady=15)
    buttons = ttk.Frame(panel)
    buttons.pack(fill="x")
    ttk.Button(buttons, text="ไม่ยินยอม / กลับ", command=dialog.destroy).pack(side="left")
    confirm = ttk.Button(buttons, text="ยินยอมและเริ่มบันทึกใบหน้า", state="disabled", command=accept, style="Primary.TButton")
    confirm.pack(side="right")
    dialog.bind("<Escape>", lambda event: dialog.destroy())
    responsive_row(buttons, minimum=310)
    wrap_labels(panel)
    dialog.grab_set()
    parent.wait_window(dialog)
    return accepted
