"""หน้าตั้งค่าการเชื่อม Google Sheets และเปิดโฟลเดอร์ข้อมูลในเครื่อง."""
import os
import queue
import subprocess
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from app_paths import DATA_DIR, is_packaged
from attendance_sheets import LOCAL_RECORDS, check_google_sheet
import google_settings
from ui_theme import ResponsivePanel, responsive_row, wrap_labels, apply_theme, page_header, window_size


def open_folder(path):
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)
        return
    env = os.environ.copy()
    if is_packaged():
        # ตัวแพ็กบน Linux เปลี่ยนค่านี้ ต้องคืนค่าเดิมก่อนเรียกโปรแกรมของระบบ
        original = env.pop("LD_LIBRARY_PATH_ORIG", None)
        env.pop("LD_LIBRARY_PATH", None)
        if original:
            env["LD_LIBRARY_PATH"] = original
    subprocess.Popen(["open" if sys.platform == "darwin" else "xdg-open", str(path)], env=env)


def current_status():
    try:
        settings = google_settings.load()
    except ValueError as exc:
        return str(exc), ""
    if settings is None:
        return f"ยังไม่ได้เชื่อม Google • บันทึกการเช็คชื่อไว้ที่ {LOCAL_RECORDS.name} ในโฟลเดอร์ข้อมูล", ""
    return f"เชื่อมกับ Google Sheet: {settings['spreadsheet']}", settings["spreadsheet"]


class SettingsWindow:
    def __init__(self, root):
        self.root = root
        self.results = queue.Queue()
        self.key_source = None
        root.title("ตั้งค่า Google Sheets")
        apply_theme(root)
        window_size(root, 760, 720, (680, 640))
        panel = ResponsivePanel(root, padding=32)
        panel.pack(fill="both", expand=True)
        page_header(panel, "เชื่อม Google Sheets", "ไม่บังคับ • ถ้าไม่เชื่อม โปรแกรมจะบันทึกการเช็คชื่อไว้ในเครื่องนี้")
        status, spreadsheet = current_status()
        self.status = tk.StringVar(value=status)
        ttk.Label(panel, textvariable=self.status, style="Summary.TLabel").pack(fill="x", pady=(0, 16))
        card = ttk.Frame(panel, style="Card.TFrame", padding=24)
        card.pack(fill="x")
        ttk.Label(card, text="ชื่อหรือลิงก์ของ Google Sheet", style="Card.TLabel").pack(anchor="w")
        self.spreadsheet = tk.StringVar(value=spreadsheet)
        ttk.Entry(card, textvariable=self.spreadsheet).pack(fill="x", pady=(6, 18))
        ttk.Label(card, text="ไฟล์ key ของ service account (.json)", style="Card.TLabel").pack(anchor="w")
        ttk.Button(card, text="เลือกไฟล์ key…", command=self.choose_key).pack(anchor="w", pady=(6, 8))
        self.key_note = tk.StringVar()
        ttk.Label(card, textvariable=self.key_note, style="CardNote.TLabel").pack(anchor="w", fill="x")
        self.show_key_email()
        self.notice = tk.StringVar()
        ttk.Label(panel, textvariable=self.notice, style="Subtitle.TLabel").pack(anchor="w", fill="x", pady=12)
        actions = ttk.Frame(panel)
        actions.pack(fill="x")
        self.save_button = ttk.Button(actions, text="ทดสอบและบันทึก", command=self.test_and_save, style="Primary.TButton")
        self.save_button.pack(side="left")
        ttk.Button(actions, text="เลิกเชื่อม Google", command=self.disconnect, style="Danger.TButton").pack(side="right")
        ttk.Label(panel, text="โฟลเดอร์ข้อมูล", style="Section.TLabel").pack(anchor="w", pady=(24, 4))
        ttk.Label(panel, text=f"{DATA_DIR}\nเก็บรายชื่อ ข้อมูลใบหน้า และผลการเช็คชื่อ ไฟล์เหล่านี้ไม่ถูกลบเมื่อถอนการติดตั้ง", style="Subtitle.TLabel").pack(anchor="w", fill="x")
        ttk.Button(panel, text="เปิดโฟลเดอร์ข้อมูล", command=lambda: open_folder(DATA_DIR)).pack(anchor="w", pady=(8, 0))
        responsive_row(actions, minimum=240)
        wrap_labels(panel)
        self.poll_id = root.after(200, self.poll_results)

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
        self.save_button.configure(state="disabled")
        self.notice.set("กำลังทดสอบการเชื่อมต่อ (อ่านอย่างเดียว)…")

        def worker():
            try:
                self.results.put(("ok", check_google_sheet(spreadsheet, key)))
            except Exception as exc:
                self.results.put(("error", str(exc) or type(exc).__name__))

        threading.Thread(target=worker, daemon=True).start()

    def poll_results(self):
        try:
            event, payload = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.save_button.configure(state="normal")
            if event == "error":
                self.notice.set(f"เชื่อมต่อไม่สำเร็จ ค่าเดิมยังไม่เปลี่ยน: {payload}")
            else:
                self.finish_save(payload)
        self.poll_id = self.root.after(200, self.poll_results)

    def finish_save(self, has_session_sheet):
        try:
            google_settings.save(self.spreadsheet.get(), self.key_source, auto_absence=has_session_sheet)
        except (OSError, ValueError) as exc:
            self.notice.set(f"บันทึกไม่สำเร็จ: {exc}")
            return
        self.key_source = None
        self.status.set(current_status()[0])
        self.show_key_email()
        self.notice.set("เชื่อมต่อสำเร็จ เปิดหน้าเช็คชื่อใหม่เพื่อใช้ค่านี้" + ("" if has_session_sheet else " • ชีตนี้ยังไม่มีระบบสรุปขาดเรียนอัตโนมัติ"))

    def disconnect(self):
        if not google_settings.is_configured():
            self.notice.set("ยังไม่ได้เชื่อม Google")
            return
        if not messagebox.askyesno("เลิกเชื่อม Google", "ลบค่าการเชื่อมและสำเนาไฟล์ key ออกจากโปรแกรมหรือไม่?\nข้อมูลใน Google Sheet จะไม่ถูกลบ", parent=self.root):
            return
        try:
            google_settings.clear()
        except OSError as exc:
            self.notice.set(f"เลิกเชื่อมไม่สำเร็จ: {exc}")
            return
        self.spreadsheet.set("")
        self.key_source = None
        self.status.set(current_status()[0])
        self.show_key_email()
        self.notice.set("เลิกเชื่อมแล้ว การเช็คชื่อครั้งต่อไปจะบันทึกในเครื่อง")


def main():
    root = tk.Tk()
    SettingsWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
