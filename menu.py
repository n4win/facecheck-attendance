import tkinter as tk
from tkinter import messagebox, ttk
import subprocess
import sys
import json
import webbrowser
from app_paths import RESOURCE_DIR, is_packaged, restore_system_libraries
from attendance_sheets import spreadsheet_url
import google_settings
from ui_theme import ResponsivePanel, apply_theme, page_header, window_size

MENU_ITEMS = (
    ("ลงทะเบียนนักศึกษา", "add_face_student"),
    ("จัดการข้อมูลนักศึกษา", "studata"),
    ("เช็คชื่อด้วยการสแกน", "scanstu"),
    ("เช็คชื่อด้วยอาจารย์ผู้สอนเอง", "kru_check"),
)
TOOL_FLAG = "--tool"
SIGN_IN_TOOLS = {"scanstu", "kru_check"}


def run_tool(name):
    # import ตรง ๆ ทีละตัว เพื่อให้ตัวแพ็กโปรแกรมรวมทุกหน้าต่างไว้ในไฟล์เดียว
    if name == "add_face_student":
        import add_face_student
        add_face_student.main()
    elif name == "studata":
        import studata
        studata.main()
    elif name == "scanstu":
        import scanstu
        scanstu.main()
    elif name == "kru_check":
        import kru_check
        kru_check.open_window()
    elif name == "settings_window":
        import settings_window
        settings_window.main()
    else:
        raise SystemExit(f"ไม่รู้จักหน้าต่าง {name}")


def tool_command(name):
    # เมื่อแพ็กแล้ว sys.executable คือตัวโปรแกรมเอง ไม่ใช่ Python
    program = [sys.executable] if is_packaged() else [sys.executable, str(RESOURCE_DIR / "menu.py")]
    return program + [TOOL_FLAG, name]


def open_script(root, filename):
    if filename in SIGN_IN_TOOLS and not google_settings.is_configured():
        if messagebox.askyesno("ต้องเข้าสู่ระบบ Google", "การเช็คชื่อจะบันทึกลงชีตบน Google Drive ของคุณ จึงต้องเข้าสู่ระบบก่อน\nไปที่หน้าเข้าสู่ระบบเลยหรือไม่?", parent=root):
            open_script(root, "settings_window")
        return
    try:
        # แยกโปรเซสเพื่อให้หน้าต่างหลักยังตอบสนองระหว่างใช้งาน
        process = subprocess.Popen(tool_command(filename))
    except OSError as exc:
        messagebox.showerror("เปิดโปรแกรมไม่ได้", f"{filename}\n{exc}", parent=root)
        return

    def check_finished():
        exit_code = process.poll()
        if exit_code is None:
            root.after(500, check_finished)
        elif exit_code != 0:
            messagebox.showerror(
                "โปรแกรมหยุดทำงาน",
                f"{filename} ปิดด้วยข้อผิดพลาด (รหัส {exit_code})\nดูรายละเอียดเพิ่มเติมใน Terminal",
                parent=root,
            )

    root.after(500, check_finished)


def open_report(root):
    try:
        config = RESOURCE_DIR / "reports" / "looker_studio_config.json"
        if not config.is_file():
            # ยังไม่ได้ตั้งค่า Looker Studio ให้เปิดชีตที่เก็บผลเช็คชื่อแทน
            sheet = spreadsheet_url(google_settings.load())
            if not sheet:
                raise RuntimeError("กรุณาเข้าสู่ระบบ Google ก่อน ผลเช็คชื่อจะอยู่ในชีตบน Drive ของคุณ")
            restore_system_libraries()
            if not webbrowser.open(sheet):
                raise RuntimeError(f"เปิดเบราว์เซอร์ไม่ได้ กรุณาเปิดลิงก์นี้เอง: {sheet}")
            return
        settings = json.loads(config.read_text(encoding="utf-8"))
        url = settings.get("saved_report_url") or settings["create_report_url"]
        if not url.startswith(("https://lookerstudio.google.com/", "https://datastudio.google.com/")):
            raise ValueError("ลิงก์รายงานต้องเป็น Looker Studio")
        if not webbrowser.open(url):
            raise RuntimeError("เปิดเบราว์เซอร์ไม่ได้ กรุณาเปิดลิงก์จากคู่มือในโฟลเดอร์ reports")
    except (OSError, ValueError, KeyError, RuntimeError) as exc:
        messagebox.showerror("เปิดรายงานไม่ได้", str(exc), parent=root)


def main():
    root = tk.Tk()
    root.title("ระบบจัดการนักศึกษาและเช็คชื่อ")
    apply_theme(root)
    window_size(root, 940, 800, (820, 720))
    panel = ResponsivePanel(root, padding=32)
    panel.pack(expand=True, fill="both")
    page_header(panel, "เริ่มต้นใช้งาน", "ลงทะเบียน จัดการรายชื่อ และเช็คชื่อในที่เดียว")
    cards = ttk.Frame(panel)
    cards.pack(fill="x")
    card_widgets = []
    card_text = []
    descriptions = (
        "เพิ่มนักศึกษาใหม่ พร้อมอ่านและยืนยัน\nความยินยอมก่อนบันทึกใบหน้า",
        "ค้นหา แก้ไขชื่อและรหัสนักศึกษา\nหรือจัดการข้อมูลใบหน้าที่บันทึกไว้",
        "ตั้งเวลาเข้าเรียนและเช็คชื่อผ่านกล้อง\nดูผลการเช็คชื่อได้ทันที",
        "เลือกนักศึกษาและระบุสถานะด้วยมือ\nพร้อมส่งข้อมูลไป Google Sheets",
    )
    for index, (label, filename) in enumerate(MENU_ITEMS):
        card = ttk.Frame(cards, style="Card.TFrame", padding=24)
        card.grid(row=index // 2, column=index % 2, sticky="nsew", padx=(0, 10) if index % 2 == 0 else (10, 0), pady=(0, 10) if index < 2 else (10, 0))
        ttk.Label(card, text=f"0{index+1}", style="Number.TLabel").pack(anchor="w")
        title = ttk.Label(card, text=label, style="CardTitle.TLabel", wraplength=330)
        title.pack(anchor="w", fill="x", pady=(8, 6))
        description = ttk.Label(card, text=descriptions[index], style="CardNote.TLabel", wraplength=330)
        description.pack(anchor="w", fill="x", pady=(0, 18))
        card_widgets.append(card)
        card_text.append((title, description))
        ttk.Button(
            card,
            text="เปิดใช้งาน  →",
            command=lambda script=filename: open_script(root, script),
            style="Primary.TButton" if index == 2 else "TButton",
        ).pack(fill="x", side="bottom")
    ttk.Button(panel, text="เปิดรายงานสรุปการเข้าเรียน ", command=lambda: open_report(root)).pack(fill="x", pady=(18, 0))
    ttk.Button(panel, text="เข้าสู่ระบบ Google และตั้งค่า", command=lambda: open_script(root, "settings_window")).pack(fill="x", pady=(10, 0))
    footer = ttk.Label(panel, text="เลือกเมนูที่ต้องการ • แต่ละเมนูเปิดเป็นหน้าต่างแยก", style="Subtitle.TLabel")
    footer.pack(anchor="w", fill="x", pady=(10, 0))
    pending_layout = None
    last_width = None

    def arrange_cards():
        nonlocal pending_layout, last_width
        pending_layout = None
        width = max(296, panel.canvas.winfo_width() - 64)
        if width == last_width:
            return
        last_width = width
        columns = 2 if width >= 720 else 1
        for column in range(2):
            cards.columnconfigure(column, weight=1 if column < columns else 0,
                                  uniform="menu" if column < columns else "", minsize=0)
        for index, card in enumerate(card_widgets):
            card.grid(row=index // columns, column=index % columns,
                      sticky="nsew", padx=4, pady=6)
            for label in card_text[index]:
                label.configure(wraplength=max(100, width // columns - 64))
        footer.configure(wraplength=width)

    def schedule_layout(event):
        nonlocal pending_layout
        if pending_layout is not None:
            root.after_cancel(pending_layout)
        pending_layout = root.after(60, arrange_cards)

    panel.canvas.bind("<Configure>", schedule_layout, add="+")
    root.after_idle(arrange_cards)
    root.mainloop()


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == TOOL_FLAG:
        run_tool(sys.argv[2])
    elif len(sys.argv) == 3 and sys.argv[1] == "--self-check":
        import self_check
        sys.exit(self_check.run(sys.argv[2], [name for _, name in MENU_ITEMS] + ["settings_window"], tool_command))
    else:
        main()
