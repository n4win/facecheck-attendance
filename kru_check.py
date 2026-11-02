"""หน้าต่างเช็คชื่อด้วยอาจารย์ผู้สอน: python3 kru_check.py"""

from datetime import date, datetime
from pathlib import Path
import pickle
import queue
import sqlite3
import threading
import uuid
import tkinter as tk
from tkinter import messagebox, ttk
from app_paths import DATA_DIR
from attendance_sheets import AttendanceSheets
import google_settings
from studata import StudentStore, FILES as ROSTER_FILES
from ui_theme import ResponsivePanel, responsive_row, wrap_labels, table_scrollbars, apply_theme, page_header, window_size, status_table


class RosterUnpickler(pickle.Unpickler):
    def find_class(self, module, name):
        raise pickle.UnpicklingError("ไฟล์รายชื่อต้องมีเฉพาะข้อมูลพื้นฐาน")


class AttendanceStore:
    def __init__(self, path=None, seed_path=None, roster=None):
        path = Path(path) if path is not None else DATA_DIR / "manual_attendance.sqlite3"
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA foreign_keys = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS students (
                id INTEGER PRIMARY KEY, student_id TEXT NOT NULL UNIQUE,
                name TEXT NOT NULL, active INTEGER NOT NULL DEFAULT 1
            );
            CREATE TABLE IF NOT EXISTS attendance (
                student INTEGER REFERENCES students(id), day TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('มา', 'มาสาย')),
                updated_at TEXT NOT NULL, PRIMARY KEY(student, day)
            );
            CREATE TABLE IF NOT EXISTS metadata (key TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS sheets_queue (
                student INTEGER REFERENCES students(id), day TEXT NOT NULL,
                status TEXT, updated_at TEXT NOT NULL, revision TEXT NOT NULL,
                PRIMARY KEY(student, day)
            );
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(students)")}
        if "roster_uid" not in columns:
            self.db.execute("ALTER TABLE students ADD COLUMN roster_uid TEXT")
        if "origin" not in columns:
            self.db.execute("ALTER TABLE students ADD COLUMN origin TEXT NOT NULL DEFAULT 'legacy'")
        self.db.commit()
        self.roster = roster if roster is not None else (StudentStore(path.parent) if seed_path is None else None)
        self.roster_stamp = None
        self.import_warning = ""
        if self.roster is None and not self.db.execute("SELECT 1 FROM metadata WHERE key='seeded'").fetchone():
            source = Path(seed_path) if seed_path is not None else DATA_DIR / "student_data.pkl"
            try:
                records = []
                if source.exists():
                    with source.open("rb") as handle:
                        records = RosterUnpickler(handle).load()
                    if not isinstance(records, list) or any(
                        not isinstance(row, dict) or not str(row.get("stu_id", "")).strip()
                        or not str(row.get("name", "")).strip() for row in records
                    ):
                        raise ValueError("รูปแบบรายชื่อเดิมไม่ถูกต้อง")
                with self.db:
                    for row in records:
                        self.db.execute(
                            "INSERT OR IGNORE INTO students(student_id, name) VALUES (?, ?)",
                            (str(row["stu_id"]).strip(), str(row["name"]).strip()),
                        )
                    self.db.execute("INSERT INTO metadata VALUES ('seeded')")
            except (OSError, ValueError, EOFError, pickle.UnpicklingError) as exc:
                self.import_warning = f"นำเข้ารายชื่อเดิมไม่ได้: {exc}\nยังสามารถเพิ่มรายชื่อเองได้"
        if self.roster is not None:
            try:
                self.sync_roster()
                self.import_warning = ""
            except Exception as exc:
                self.import_warning = f"ซิงก์รายชื่อนักศึกษาไม่สำเร็จ: {exc}"

    def source_stamp(self):
        return tuple((path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else None
                     for path in (self.roster.directory / filename for filename in ROSTER_FILES))

    def sync_roster(self):
        if self.roster is None or self.source_stamp() == self.roster_stamp:
            return False
        records = self.roster.sync_rows()
        ids = [str(row["stu_id"]).strip() for row in records]
        if any(not student_id for student_id in ids) or len(set(ids)) != len(ids):
            raise ValueError("รหัสนักศึกษาในข้อมูลต้นทางว่างหรือซ้ำ กรุณาแก้ไขในหน้าข้อมูลนักศึกษา")
        existing = [dict(row) for row in self.db.execute("SELECT * FROM students")]
        claimed = set()
        assignments = []
        for record, student_id in zip(records, ids):
            match = next((row for row in existing if row["roster_uid"] == record["_roster_uid"]), None)
            if match is None:
                candidates = [row for row in existing if row["id"] not in claimed and not row["roster_uid"]
                              and row["student_id"] == student_id]
                if not candidates:
                    candidates = [row for row in existing if row["id"] not in claimed and not row["roster_uid"]
                                  and row["name"] == record["name"]]
                match = candidates[0] if len(candidates) == 1 else None
            if match is not None:
                claimed.add(match["id"])
            assignments.append((record, student_id, match))
        with self.db:
            # รักษา id ภายในไว้เพื่อไม่ให้ประวัติหลุดเมื่อเปลี่ยนรหัสนักศึกษา
            for row in existing:
                if row["id"] in claimed:
                    self.db.execute("UPDATE students SET student_id=? WHERE id=?", (f"sync:{uuid.uuid4().hex}", row["id"]))
                elif row["origin"] != "manual":
                    self.db.execute("UPDATE students SET active=0 WHERE id=?", (row["id"],))
            for record, student_id, match in assignments:
                conflict = self.db.execute("SELECT id FROM students WHERE student_id=?", (student_id,)).fetchone()
                if conflict:
                    raise ValueError(f"รหัส {student_id} มีประวัติของบุคคลอื่นอยู่แล้ว กรุณาตรวจสอบรหัสก่อนซิงก์")
                if match:
                    self.db.execute("UPDATE students SET student_id=?, name=?, active=1, roster_uid=?, origin='roster' WHERE id=?",
                                    (student_id, record["name"], record["_roster_uid"], match["id"]))
                else:
                    self.db.execute("INSERT INTO students(student_id, name, roster_uid, origin) VALUES (?, ?, ?, 'roster')",
                                    (student_id, record["name"], record["_roster_uid"]))
        self.roster_stamp = self.source_stamp()
        return True

    def add(self, student_id, name):
        self.sync_roster()
        student_id, name = student_id.strip(), name.strip()
        if not student_id or not name:
            raise ValueError("กรุณากรอกรหัสนักเรียนและชื่อ-นามสกุล")
        with self.db:
            existing = self.db.execute(
                "SELECT id, active FROM students WHERE student_id=?", (student_id,)
            ).fetchone()
            if existing:
                raise ValueError("รหัสนี้มีอยู่แล้วหรือเคยถูกลบ กรุณาใช้รหัสใหม่")
            self.db.execute("INSERT INTO students(student_id, name, origin) VALUES (?, ?, 'manual')", (student_id, name))

    def remove(self, student):
        self.sync_roster()
        row = self.db.execute("SELECT origin FROM students WHERE id=?", (student,)).fetchone()
        if row and row["origin"] == "roster":
            raise ValueError("รายชื่อนี้ซิงก์จากข้อมูลนักศึกษา กรุณาลบผ่านหน้า ข้อมูลนักศึกษา เพื่อให้ทั้งสองหน้าตรงกัน")
        with self.db:
            self.db.execute("UPDATE students SET active=0 WHERE id=?", (student,))

    def mark(self, student, day, status):
        self.sync_roster()
        date.fromisoformat(day)
        if status not in ("มา", "มาสาย", None):
            raise ValueError("สถานะไม่ถูกต้อง")
        timestamp = datetime.now().strftime("%H:%M:%S")
        with self.db:
            if not self.db.execute("SELECT 1 FROM students WHERE id=? AND active=1", (student,)).fetchone():
                raise ValueError("ไม่พบรายชื่อนี้ กรุณาโหลดรายชื่อใหม่")
            if status is None:
                self.db.execute("DELETE FROM attendance WHERE student=? AND day=?", (student, day))
            else:
                self.db.execute("""
                    INSERT INTO attendance VALUES (?, ?, ?, ?)
                    ON CONFLICT(student, day) DO UPDATE SET
                        status=excluded.status, updated_at=excluded.updated_at
                """, (student, day, status, timestamp))
            self.db.execute("""
                INSERT INTO sheets_queue VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(student, day) DO UPDATE SET status=excluded.status,
                    updated_at=excluded.updated_at, revision=excluded.revision
            """, (student, day, status, timestamp, uuid.uuid4().hex))

    def pending(self):
        return [dict(row) for row in self.db.execute("""
            SELECT q.*, s.student_id, s.name FROM sheets_queue q
            JOIN students s ON s.id=q.student ORDER BY q.day, q.student
        """)]

    def acknowledge(self, item):
        with self.db:
            self.db.execute("DELETE FROM sheets_queue WHERE student=? AND day=? AND revision=?",
                            (item["student"], item["day"], item["revision"]))

    def rows(self, day):
        self.sync_roster()
        return self.db.execute("""
            SELECT s.id, s.student_id, s.name, COALESCE(a.status, 'ยังไม่เช็ค') AS status,
                   COALESCE(a.updated_at, '—') AS updated_at
            FROM students s LEFT JOIN attendance a ON a.student=s.id AND a.day=?
            WHERE s.active=1 ORDER BY s.name, s.student_id
        """, (day,)).fetchall()

    def close(self):
        self.db.close()


class AttendanceWindow:
    def __init__(self, root, store):
        self.root, self.store = root, store
        self.sheets = AttendanceSheets()
        self.destination = "Google Sheets" if google_settings.is_configured() else "ไฟล์ในเครื่อง"
        self.absence_summary = google_settings.absence_summary_enabled()
        self.sync_results = queue.Queue()
        self.syncing = False
        self.round_opening = False
        self.opened_days = set()
        self.round_ids = {}
        self.day = date.today().isoformat()
        root.title("เช็คชื่อด้วยอาจารย์ผู้สอน")
        apply_theme(root)
        window_size(root, 1100, 850, (1000, 740))
        frame = ResponsivePanel(root, padding=28)
        frame.pack(fill="both", expand=True)
        page_header(frame, "เช็คชื่อด้วยอาจารย์ผู้สอน", f"เลือกวันที่และนักศึกษา แล้วระบุสถานะ • บันทึกลง {self.destination} อัตโนมัติ")

        toolbar = ttk.Frame(frame)
        toolbar.pack(fill="x")
        ttk.Label(toolbar, text="วันที่ (ปี-เดือน-วัน ค.ศ.)").pack(side="left")
        self.date_var = tk.StringVar(value=self.day)
        entry = ttk.Entry(toolbar, textvariable=self.date_var, width=13)
        entry.pack(side="left", padx=8)
        entry.bind("<Return>", lambda event: self.change_day())
        ttk.Button(toolbar, text="แสดงวันที่", command=self.change_day).pack(side="left")
        ttk.Button(toolbar, text="วันนี้", command=self.today).pack(side="left", padx=6)
        ttk.Button(toolbar, text="ซิงก์รายชื่อนักศึกษา", command=self.refresh).pack(side="left", padx=6)
        self.day_label = ttk.Label(frame)
        self.day_label.pack(anchor="w", pady=(10, 4))
        self.summary = ttk.Label(frame, style="Summary.TLabel")
        self.summary.pack(fill="x", pady=10)
        search_bar = ttk.Frame(frame)
        search_bar.pack(fill="x", pady=8)
        ttk.Label(search_bar, text="ค้นหาชื่อ / รหัส").pack(side="left", padx=(0, 8))
        self.search = tk.StringVar()
        ttk.Entry(search_bar, textvariable=self.search).pack(side="left", fill="x", expand=True)
        self.search.trace_add("write", lambda *_: self.refresh())

        table = ttk.Frame(frame)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("student_id", "name", "status", "updated_at"), show="headings", selectmode="browse")
        for column, label, width in (("student_id", "รหัสนักศึกษา", 130), ("name", "ชื่อ-นามสกุล", 290), ("status", "สถานะ", 120), ("updated_at", "เวลาที่บันทึก", 120)):
            self.tree.heading(column, text=label)
            self.tree.column(column, width=width, minwidth=90)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        status_table(self.tree)
        self.tree.bind("<<TreeviewSelect>>", self.selection_changed)
        actions = ttk.Frame(frame)
        actions.pack(fill="x", pady=10)
        self.open_round_button = ttk.Button(actions, text="เปิดรอบเช็คชื่อ", command=self.open_round, style="Primary.TButton")
        self.open_round_button.pack(side="left", padx=(0, 8))
        self.selection_buttons = []
        for label, callback, style in (("มา", lambda: self.mark("มา"), "Success.TButton"), ("มาสาย", lambda: self.mark("มาสาย"), "Warning.TButton"), ("ยกเลิกการเช็ค", lambda: self.mark(None), "TButton")):
            button = ttk.Button(actions, text=label, command=callback, state="disabled", style=style)
            button.pack(side="left", padx=(0, 8))
            self.selection_buttons.append(button)

        sync_bar = ttk.Frame(frame)
        sync_bar.pack(fill="x", pady=(8, 0))
        self.sync_status = tk.StringVar(value=f"{self.destination}: พร้อมบันทึกข้อมูลเมื่อเช็คชื่อ")
        ttk.Label(sync_bar, textvariable=self.sync_status, style="Subtitle.TLabel").pack(side="left")
        self.notice = tk.StringVar(value="กดเปิดรอบก่อนเช็คชื่อ • Google จะสรุปขาดเรียนหลังข้ามวัน แม้ไม่มีผู้มาเช็คชื่อ" if self.absence_summary else "กดเปิดรอบก่อนเช็คชื่อ")
        ttk.Label(frame, textvariable=self.notice, style="Subtitle.TLabel", wraplength=960).pack(anchor="w", pady=(12, 0))
        for row in (toolbar, actions, sync_bar):
            responsive_row(row, minimum=190)
        table_scrollbars(table, self.tree)
        wrap_labels(frame)
        root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        if store.import_warning:
            messagebox.showwarning("นำเข้ารายชื่อ", store.import_warning, parent=root)
        self.poll_id = root.after(200, self.poll_sync)
        self.roster_poll_id = root.after(2000, self.poll_roster)
        self.start_sync()

    def poll_roster(self):
        try:
            if not self.syncing and not self.round_opening and self.store.sync_roster():
                self.refresh()
                self.notice.set("ซิงก์ชื่อและรหัสล่าสุดจากหน้าข้อมูลนักศึกษาแล้ว")
        except Exception as exc:
            self.notice.set(f"ซิงก์รายชื่อไม่สำเร็จ: {exc}")
        finally:
            self.roster_poll_id = self.root.after(2000, self.poll_roster)

    def start_sync(self):
        if self.syncing or self.round_opening:
            return
        pending = self.store.pending()
        if not pending:
            return
        self.syncing = True
        self.sync_status.set(f"{self.destination}: กำลังบันทึก {len(pending)} รายการ…")

        def worker():
            for item in pending:
                try:
                    self.sheets.send(item)
                except Exception as exc:
                    self.sync_results.put(("error", str(exc)))
                    return
                self.sync_results.put(("sent", item))
            self.sync_results.put(("done", None))

        threading.Thread(target=worker, daemon=True).start()

    def open_round(self):
        if self.syncing or self.round_opening:
            self.notice.set("กำลังส่งข้อมูล กรุณารอให้เสร็จก่อนเปิดรอบ")
            return
        if not self.change_day():
            return
        day = self.day
        if day in self.opened_days:
            self.notice.set(f"เปิดรอบวันที่ {day} แล้ว")
            return
        try:
            students = [{"name": r["name"], "student_id": r["student_id"]} for r in self.store.rows(day)]
        except Exception as exc:
            self.notice.set(f"เปิดรอบไม่ได้: {exc}")
            return
        session_id = self.round_ids.setdefault(day, uuid.uuid4().hex)
        self.round_opening = True
        self.open_round_button.configure(state="disabled")
        self.notice.set(f"กำลังเปิดรอบวันที่ {day} บน Google…" if self.absence_summary else f"กำลังเปิดรอบวันที่ {day}…")

        def worker():
            try:
                self.sheets.open_session(session_id, date.fromisoformat(day).strftime("%d-%m-%Y"), students)
                self.sync_results.put(("round_opened", day))
            except Exception as exc:
                self.sync_results.put(("round_error", str(exc)))

        threading.Thread(target=worker, daemon=True).start()

    def poll_sync(self):
        try:
            while True:
                event, payload = self.sync_results.get_nowait()
                if event in ("round_opened", "round_error"):
                    self.round_opening = False
                    self.open_round_button.configure(state="normal")
                    if event == "round_opened":
                        self.opened_days.add(payload)
                        self.notice.set(f"เปิดรอบวันที่ {payload} แล้ว • Google จะสรุปขาดเรียนหลังข้ามวัน" if self.absence_summary else f"เปิดรอบวันที่ {payload} แล้ว")
                    else:
                        self.notice.set(f"เปิดรอบไม่สำเร็จ: {payload}")
                    self.start_sync()
                    continue
                if event == "sent":
                    self.store.acknowledge(payload)
                else:
                    self.syncing = False
                    pending_count = len(self.store.pending())
                    if event == "error":
                        self.sync_status.set(f"{self.destination}: บันทึกไม่สำเร็จ • ค้าง {pending_count} รายการ")
                        self.notice.set(f"ข้อมูลยังอยู่ในเครื่อง จะลองส่งเมื่อเช็คชื่อหรือเปิดหน้านี้ครั้งถัดไป: {payload}")
                    else:
                        self.sync_status.set(f"{self.destination}: บันทึกสำเร็จแล้ว")
                        self.start_sync()
        except queue.Empty:
            pass
        except sqlite3.Error as exc:
            self.sync_status.set(f"{self.destination}: เก็บผลการบันทึกไม่สำเร็จ")
            self.notice.set(str(exc))
        self.poll_id = self.root.after(200, self.poll_sync)

    def selection_changed(self, event=None):
        for button in self.selection_buttons:
            button.configure(state="normal" if self.tree.selection() else "disabled")

    def refresh(self):
        selected = self.tree.selection()
        try:
            rows = self.store.rows(self.day)
        except Exception as exc:
            self.notice.set(f"โหลดรายชื่อไม่สำเร็จ: {exc}")
            return
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().strip().casefold()
        for row in rows:
            if query in row["name"].casefold() or query in row["student_id"].casefold():
                self.tree.insert("", "end", iid=str(row["id"]), values=tuple(row)[1:], tags=(row["status"],))
        if selected and self.tree.exists(selected[0]):
            self.tree.selection_set(selected[0])
        self.selection_changed()
        counts = {status: sum(row["status"] == status for row in rows) for status in ("มา", "มาสาย", "ยังไม่เช็ค")}
        self.day_label.configure(text=f"กำลังเช็คชื่อวันที่ {self.day}")
        self.summary.configure(text=f"ทั้งหมด {len(rows)} คน    •    มา {counts['มา']}    •    มาสาย {counts['มาสาย']}    •    ยังไม่เช็ค {counts['ยังไม่เช็ค']}")

    def change_day(self):
        try:
            value = date.fromisoformat(self.date_var.get().strip()).isoformat()
        except ValueError:
            messagebox.showerror("วันที่ไม่ถูกต้อง", "กรุณาใช้รูปแบบ YYYY-MM-DD เช่น 2026-09-14", parent=self.root)
            return False
        self.day = value
        self.date_var.set(value)
        self.refresh()
        return True

    def today(self):
        self.date_var.set(date.today().isoformat())
        self.change_day()

    def save_action(self, action, notice):
        try:
            action()
        except (sqlite3.Error, ValueError, OSError, pickle.UnpicklingError, EOFError) as exc:
            messagebox.showerror("บันทึกไม่สำเร็จ", str(exc), parent=self.root)
            return False
        self.refresh()
        self.notice.set(notice)
        return True

    def mark(self, status):
        selected = self.tree.selection()
        if not selected:
            return
        if self.date_var.get().strip() != self.day and not self.change_day():
            return
        if status is not None and self.day not in self.opened_days:
            self.notice.set("กรุณากดเปิดรอบเช็คชื่อและรอให้สำเร็จก่อนบันทึกสถานะ")
            return
        name = self.tree.item(selected[0], "values")[1]
        if status is None and not messagebox.askyesno(
            "ยกเลิกการเช็คชื่อ", f"ยกเลิกการเช็คชื่อ {name} วันที่ {self.day}?\nจะลบแถวของรหัสนี้และวันที่นี้ใน {self.destination} ด้วย รวมถึงแถวที่มาจากการสแกนใบหน้า", parent=self.root
        ):
            return
        if self.save_action(lambda: self.store.mark(int(selected[0]), self.day, status), f"บันทึกในเครื่องแล้ว: {name} — {status or 'ยังไม่เช็ค'} ({self.day})"):
            self.start_sync()

    def close(self):
        if self.round_opening:
            messagebox.showinfo("กำลังเปิดรอบ", "กรุณารอผลการเปิดรอบบน Google ก่อนปิดหน้าต่าง", parent=self.root)
            return
        if self.store.pending() and not messagebox.askyesno(
            "ยังมีรายการรอส่ง", f"ยังมีข้อมูลรอส่ง {self.destination} ต้องการปิดหรือไม่?\nโปรแกรมจะลองส่งรายการค้างเมื่อเปิดหน้าเช็คชื่อครั้งถัดไป", parent=self.root
        ):
            return
        self.root.after_cancel(self.poll_id)
        self.root.after_cancel(self.roster_poll_id)
        self.store.close()
        self.root.destroy()


def open_window(parent=None):
    root = tk.Toplevel(parent) if parent is not None else tk.Tk()
    try:
        store = AttendanceStore()
        AttendanceWindow(root, store)
    except (sqlite3.Error, OSError) as exc:
        messagebox.showerror("เปิดหน้าเช็คชื่อไม่ได้", str(exc), parent=root)
        root.destroy()
        return
    if parent is None:
        root.mainloop()


if __name__ == "__main__":
    open_window()
