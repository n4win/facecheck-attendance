"""หน้าเข้าสู่ระบบ Google การเชื่อมด้วยไฟล์ key แบบขั้นสูง และโฟลเดอร์ข้อมูลในเครื่อง."""
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
import webbrowser

from app_paths import ABSENCE_SCRIPT_PATH, DATA_DIR, restore_system_libraries
from attendance_sheets import check_google_sheet, spreadsheet_url
import google_auth
import google_settings
from ui_theme import ResponsivePanel, responsive_row, wrap_labels, apply_theme, page_header, window_size


def open_folder(path):
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)
        return
    restore_system_libraries()
    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)])


def current_status():
    try:
        settings = google_settings.load()
    except ValueError as exc:
        return str(exc)
    if settings is None:
        return "ยังไม่ได้เข้าสู่ระบบ • ต้องเข้าสู่ระบบก่อนจึงจะเช็คชื่อได้"
    if "spreadsheet_id" in settings:
        absence = "" if settings.get("auto_absence") else " • ยังไม่ได้ติดตั้งระบบสรุปขาดเรียนอัตโนมัติ"
        return f"เข้าสู่ระบบแล้ว: {settings.get('account') or 'บัญชี Google'} • บันทึกลงชีต {google_auth.SHEET_TITLE}{absence}"
    return f"เชื่อมด้วยไฟล์ key กับ Google Sheet: {settings['spreadsheet']}"


ABSENCE_STEPS = """ไม่บังคับ • เพิ่มคนที่ไม่มาเป็นขาดเรียนหลังเวลาเลิกเรียน แม้ปิดคอมพิวเตอร์ ทำครั้งเดียว:
1. กดปุ่มด้านล่าง โปรแกรมจะคัดลอกโค้ดและเปิดชีตให้
2. ในชีต ไปที่ ส่วนขยาย → Apps Script แล้วลบโค้ดเดิมและวางโค้ดที่คัดลอกไว้ จากนั้นกดบันทึก
3. เลือกฟังก์ชัน setupAttendanceAutomation กดเรียกใช้ แล้วกดอนุญาต ถ้า Google เตือนว่ายังไม่ได้ยืนยันแอป ให้กด Advanced แล้วกดชื่อโปรเจกต์เพื่อไปต่อ สคริปต์นี้อยู่ในบัญชีของคุณเอง
4. กลับมาที่หน้านี้ แล้วกด ตรวจการเชื่อมต่อ

ถ้าขึ้นว่าเปิดไฟล์ไม่ได้ อาจเป็นเพราะเบราว์เซอร์ล็อกอินหลายบัญชี ให้ทำในหน้าต่างไม่ระบุตัวตน และล็อกอินเฉพาะบัญชีนี้"""


class SettingsWindow:
    def __init__(self, root):
        self.root = root
        self.results = queue.Queue()
        self.key_source = None
        self.busy = False
        root.title("เข้าสู่ระบบ Google")
        apply_theme(root)
        window_size(root, 760, 780, (680, 640))
        panel = ResponsivePanel(root, padding=32)
        panel.pack(fill="both", expand=True)
        page_header(panel, "เข้าสู่ระบบ Google", "ผลเช็คชื่อจะอยู่ในชีตบน Drive ของคุณเอง • โปรแกรมเข้าถึงเฉพาะไฟล์ที่ใช้กับโปรแกรมนี้")
        self.status = tk.StringVar(value=current_status())
        ttk.Label(panel, textvariable=self.status, style="Summary.TLabel").pack(fill="x", pady=(0, 16))
        actions = ttk.Frame(panel)
        actions.pack(fill="x")
        self.sign_in_button = ttk.Button(actions, text="เข้าสู่ระบบด้วย Google", command=self.sign_in, style="Primary.TButton")
        self.sign_in_button.pack(side="left", padx=(0, 8))
        self.check_button = ttk.Button(actions, text="ตรวจการเชื่อมต่อ", command=self.check_connection)
        self.check_button.pack(side="left", padx=(0, 8))
        self.open_button = ttk.Button(actions, text="เปิดชีตของฉัน", command=self.open_sheet)
        self.open_button.pack(side="left", padx=(0, 8))
        ttk.Button(actions, text="ออกจากระบบ", command=self.sign_out, style="Danger.TButton").pack(side="right")
        self.notice = tk.StringVar()
        ttk.Label(panel, textvariable=self.notice, style="Subtitle.TLabel").pack(anchor="w", fill="x", pady=12)

        self.show_advanced = tk.BooleanVar(value=False)
        ttk.Checkbutton(panel, text="ขั้นสูง: เชื่อมชีตที่มีอยู่ด้วยไฟล์ key ของ service account", variable=self.show_advanced,
                        command=self.toggle_advanced).pack(anchor="w")
        self.advanced_anchor = ttk.Frame(panel)
        self.advanced_anchor.pack(fill="x")
        self.advanced = ttk.Frame(self.advanced_anchor, style="Card.TFrame", padding=24)
        ttk.Label(self.advanced, text="ชื่อหรือลิงก์ของ Google Sheet", style="Card.TLabel").pack(anchor="w")
        self.spreadsheet = tk.StringVar(value=self.key_mode_spreadsheet())
        ttk.Entry(self.advanced, textvariable=self.spreadsheet).pack(fill="x", pady=(6, 18))
        ttk.Label(self.advanced, text="ไฟล์ key ของ service account (.json)", style="Card.TLabel").pack(anchor="w")
        ttk.Button(self.advanced, text="เลือกไฟล์ key…", command=self.choose_key).pack(anchor="w", pady=(6, 8))
        self.key_note = tk.StringVar()
        ttk.Label(self.advanced, textvariable=self.key_note, style="CardNote.TLabel").pack(anchor="w", fill="x")
        self.show_key_email()
        self.save_button = ttk.Button(self.advanced, text="ทดสอบและบันทึก", command=self.test_and_save)
        self.save_button.pack(anchor="w", pady=(12, 0))

        ttk.Label(panel, text="สรุปขาดเรียนอัตโนมัติ", style="Section.TLabel").pack(anchor="w", pady=(24, 4))
        ttk.Label(panel, text=ABSENCE_STEPS, style="Subtitle.TLabel").pack(anchor="w", fill="x")
        self.absence_button = ttk.Button(panel, text="เปิดระบบสรุปขาดเรียน", command=self.start_absence_setup)
        self.absence_button.pack(anchor="w", pady=(8, 0))

        ttk.Label(panel, text="โฟลเดอร์ข้อมูลในเครื่อง", style="Section.TLabel").pack(anchor="w", pady=(24, 4))
        ttk.Label(panel, text=f"{DATA_DIR}\nเก็บรายชื่อ ข้อมูลใบหน้า และหลักฐานความยินยอม ไฟล์เหล่านี้ไม่ถูกลบเมื่อถอนการติดตั้ง", style="Subtitle.TLabel").pack(anchor="w", fill="x")
        ttk.Button(panel, text="เปิดโฟลเดอร์ข้อมูล", command=lambda: open_folder(DATA_DIR)).pack(anchor="w", pady=(8, 0))
        responsive_row(actions, minimum=200)
        wrap_labels(panel)
        self.update_buttons()
        self.poll_id = root.after(200, self.poll_results)

    def settings(self):
        try:
            return google_settings.load()
        except ValueError:
            return None

    def key_mode_spreadsheet(self):
        settings = self.settings()
        return settings.get("spreadsheet", "") if settings else ""

    def update_buttons(self):
        settings = self.settings()
        signed_in = settings is not None and "spreadsheet_id" in settings
        state = "disabled" if self.busy else "normal"
        self.sign_in_button.configure(state=state)
        self.save_button.configure(state=state)
        self.check_button.configure(state=state if signed_in else "disabled")
        self.open_button.configure(state="normal" if settings_has_link(settings) else "disabled")
        self.absence_button.configure(state="normal" if settings_has_link(settings) else "disabled")

    def toggle_advanced(self):
        if self.show_advanced.get():
            self.advanced.pack(fill="x", pady=(8, 0))
        else:
            self.advanced.pack_forget()

    def run_in_background(self, notice, on_success, work):
        self.busy = True
        self.update_buttons()
        self.notice.set(notice)

        def worker():
            try:
                self.results.put((on_success, work()))
            except Exception as exc:
                self.results.put((None, str(exc) or type(exc).__name__))

        threading.Thread(target=worker, daemon=True).start()

    def poll_results(self):
        try:
            on_success, payload = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            if on_success is None:
                self.notice.set(f"ไม่สำเร็จ ค่าเดิมยังไม่เปลี่ยน: {payload}")
            else:
                on_success(payload)
            self.status.set(current_status())
            self.update_buttons()
        self.poll_id = self.root.after(200, self.poll_results)

    def sign_in(self):
        self.run_in_background("กรุณาเข้าสู่ระบบและกดอนุญาตในเบราว์เซอร์ที่เปิดขึ้นมา…", self.signed_in, google_auth.sign_in)

    def signed_in(self, details):
        self.spreadsheet.set("")
        self.notice.set("เข้าสู่ระบบสำเร็จ ถ้าเปิดหน้าเช็คชื่อค้างไว้ ให้ปิดแล้วเปิดใหม่")

    def check_connection(self):
        self.run_in_background("กำลังตรวจการเชื่อมต่อ (อ่านอย่างเดียว)…", self.checked, google_auth.refresh_status)

    def checked(self, installed):
        self.notice.set("เชื่อมต่อได้ • พบระบบสรุปขาดเรียนอัตโนมัติ" if installed else "เชื่อมต่อได้ • ยังไม่พบระบบสรุปขาดเรียนอัตโนมัติ")

    def open_sheet(self):
        url = spreadsheet_url(self.settings())
        if url:
            restore_system_libraries()
            webbrowser.open(url)

    def start_absence_setup(self):
        try:
            code = ABSENCE_SCRIPT_PATH.read_text(encoding="utf-8")
        except OSError as exc:
            self.notice.set(f"อ่านโค้ดระบบสรุปขาดเรียนไม่ได้: {exc}")
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(code)
        self.root.update()
        self.open_sheet()
        self.notice.set("คัดลอกโค้ดแล้ว และเปิดชีตให้แล้ว ทำตามขั้นตอนด้านล่างโดยยังไม่ต้องปิดหน้าต่างนี้")

    def sign_out(self):
        if not google_settings.is_configured():
            self.notice.set("ยังไม่ได้เข้าสู่ระบบ")
            return
        if not messagebox.askyesno("ออกจากระบบ", "ลบการเข้าสู่ระบบออกจากเครื่องนี้หรือไม่?\nชีตใน Google Drive จะไม่ถูกลบ และรายการที่ยังส่งไม่สำเร็จจะรอจนกว่าจะเข้าสู่ระบบอีกครั้ง", parent=self.root):
            return
        try:
            revoked = google_auth.sign_out()
        except (OSError, ValueError) as exc:
            self.notice.set(f"ออกจากระบบไม่สำเร็จ: {exc}")
            return
        self.spreadsheet.set("")
        self.key_source = None
        self.status.set(current_status())
        self.show_key_email()
        self.update_buttons()
        self.notice.set("ออกจากระบบแล้ว" if revoked else "ออกจากระบบในเครื่องแล้ว แต่ติดต่อ Google เพื่อยกเลิกสิทธิ์ไม่ได้ ยกเลิกเองได้จากหน้าบัญชี Google")

    def show_key_email(self):
        path = self.key_source or (google_settings.KEY_PATH if google_settings.KEY_PATH.is_file() else None)
        if path is None:
            self.key_note.set("ยังไม่ได้เลือกไฟล์")
            return
        try:
            self.key_note.set(f"แชร์ชีตให้อีเมลนี้เป็น Editor:\n{google_settings.key_email(path)}")
        except ValueError as exc:
            self.key_note.set(str(exc))

    def choose_key(self):
        path = filedialog.askopenfilename(parent=self.root, title="เลือกไฟล์ key", filetypes=[("JSON", "*.json")])
        if path:
            self.key_source = path
            self.show_key_email()

    def test_and_save(self):
        spreadsheet = self.spreadsheet.get().strip()
        key = self.key_source or google_settings.KEY_PATH
        try:
            if not spreadsheet:
                raise ValueError("กรุณาระบุชื่อหรือลิงก์ของ Google Sheet")
            google_settings.key_email(key)
        except ValueError as exc:
            self.notice.set(str(exc))
            return
        self.run_in_background("กำลังทดสอบการเชื่อมต่อ (อ่านอย่างเดียว)…", self.finish_save, lambda: check_google_sheet(spreadsheet, key))

    def finish_save(self, has_session_sheet):
        try:
            # เปลี่ยนมาใช้ key แล้ว จึงไม่เก็บการเข้าสู่ระบบเดิมไว้ในเครื่อง
            google_auth.delete_refresh_token()
            google_settings.save(self.spreadsheet.get(), self.key_source, auto_absence=has_session_sheet)
        except (OSError, ValueError) as exc:
            self.notice.set(f"บันทึกไม่สำเร็จ: {exc}")
            return
        self.key_source = None
        self.show_key_email()
        self.notice.set("เชื่อมต่อสำเร็จ ถ้าเปิดหน้าเช็คชื่อค้างไว้ ให้ปิดแล้วเปิดใหม่" + ("" if has_session_sheet else " • ชีตนี้ยังไม่มีระบบสรุปขาดเรียนอัตโนมัติ"))


def settings_has_link(settings):
    return bool(spreadsheet_url(settings))


def main():
    root = tk.Tk()
    SettingsWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
