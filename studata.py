"""ดูและจัดการนักศึกษาที่ลงทะเบียนใบหน้า: python studata.py"""
from pathlib import Path
import os
import pickle
import tempfile
import uuid
import tkinter as tk
from tkinter import messagebox, ttk
from app_paths import DATA_DIR
from ui_theme import ResponsivePanel, responsive_row, wrap_labels, table_scrollbars, apply_theme, page_header, window_size

FILES = ("student_data.pkl", "names.pkl", "faces_data.pkl")


class StudentStore:
    def __init__(self, directory=DATA_DIR):
        self.directory = Path(directory)

    def load(self):
        raw = {name: (self.directory / name).read_bytes() if (self.directory / name).exists() else None for name in FILES}
        if not any(value is not None for value in raw.values()):
            return [], [], [], raw
        # Unknown อาจถูกบันทึกก่อนมีนักศึกษาคนแรก จึงยังไม่มี student_data.pkl
        if raw["names.pkl"] is None or raw["faces_data.pkl"] is None:
            raise ValueError("ข้อมูลใบหน้าไม่ครบ กรุณาตรวจสอบ names.pkl และ faces_data.pkl")
        students = pickle.loads(raw["student_data.pkl"]) if raw["student_data.pkl"] is not None else []
        labels = pickle.loads(raw["names.pkl"])
        faces = pickle.loads(raw["faces_data.pkl"])
        if not isinstance(students, list) or any(
            not isinstance(row, dict) or not isinstance(row.get("name"), str)
            or "stu_id" not in row for row in students
        ):
            raise ValueError("รูปแบบข้อมูลนักศึกษาไม่ถูกต้อง")
        if len(labels) != len(faces) or any(not isinstance(label, str) for label in labels):
            raise ValueError("จำนวนชื่อกับภาพใบหน้าไม่ตรงกัน กรุณาตรวจสอบข้อมูลก่อนแก้ไข")
        return students, list(labels), faces, raw

    def rows(self):
        students, labels, _, _ = self.load()
        registered = set(labels)
        return [dict(row) for row in students
                if row["name"].strip().casefold() != "unknown" and row["name"] in registered]

    def sync_rows(self):
        """ให้แต่ละคนมีตัวระบุคงที่ แม้เปลี่ยนทั้งชื่อและรหัสนักศึกษา."""
        students, labels, faces, raw = self.load()
        registered = set(labels)
        changed = False
        for row in students:
            if not row.get("_roster_uid"):
                row["_roster_uid"] = uuid.uuid4().hex
                changed = True
        if changed:
            self.save((students, labels, faces), raw)
        return [dict(row) for row in students
                if row["name"].strip().casefold() != "unknown" and row["name"] in registered]

    def change(self, original, name=None, student_id=None):
        students, labels, faces, raw = self.load()
        matches = [i for i, row in enumerate(students)
                   if {k: v for k, v in row.items() if k != "_roster_uid"}
                   == {k: v for k, v in original.items() if k != "_roster_uid"}]
        if len(matches) != 1:
            raise ValueError("ข้อมูลรายการนี้เปลี่ยนแล้ว กรุณาโหลดรายชื่อใหม่")
        old_name = original["name"]
        if old_name.strip().casefold() == "unknown" or old_name not in labels:
            raise ValueError("ไม่พบข้อมูลใบหน้าของนักศึกษารายการนี้")
        if sum(row["name"] == old_name for row in students) != 1:
            raise ValueError("มีนักศึกษาชื่อซ้ำกัน ระบบเดิมผูกใบหน้าด้วยชื่อ จึงยังแยกข้อมูลของแต่ละคนไม่ได้")
        index = matches[0]
        if name is None:
            import numpy as np
            keep = [i for i, label in enumerate(labels) if label != old_name]
            labels = [labels[i] for i in keep]
            faces = np.asarray(faces)[keep]
            del students[index]
        else:
            name, student_id = name.strip(), student_id.strip()
            if not name or not student_id:
                raise ValueError("กรุณากรอกชื่อ-นามสกุลและรหัสนักศึกษา")
            if name.casefold() == "unknown":
                raise ValueError("ไม่สามารถเปลี่ยนชื่อนักศึกษาเป็น Unknown ได้")
            if any(str(row["stu_id"]) == student_id for i, row in enumerate(students) if i != index):
                raise ValueError("รหัสนักศึกษานี้มีอยู่แล้ว")
            if name != old_name and (name in labels or any(row["name"] == name for row in students)):
                raise ValueError("ชื่อนี้มีอยู่แล้ว กรุณาใช้ชื่อที่แยกบุคคลได้ชัดเจน")
            students[index] = {**students[index], "name": name, "stu_id": student_id}
            labels = [name if label == old_name else label for label in labels]
        self.save((students, labels, faces), raw)

    def save(self, values, original):
        # เตรียมไฟล์ทั้งหมดก่อนแทนที่ และคืนค่าเดิมถ้าการเขียนบางไฟล์ล้มเหลว
        prepared, replaced = {}, []
        try:
            for filename, value in zip(FILES, values):
                with tempfile.NamedTemporaryFile(dir=self.directory, delete=False) as handle:
                    prepared[filename] = Path(handle.name)
                    pickle.dump(value, handle, protocol=pickle.HIGHEST_PROTOCOL)
                    handle.flush()
                    os.fsync(handle.fileno())
            for filename in FILES:
                path = self.directory / filename
                current = path.read_bytes() if path.exists() else None
                if current != original[filename]:
                    raise ValueError("ข้อมูลถูกแก้ไขจากหน้าอื่น กรุณาโหลดรายชื่อใหม่แล้วลองอีกครั้ง")
            try:
                for filename in FILES:
                    prepared[filename].replace(self.directory / filename)
                    replaced.append(filename)
            except OSError:
                for filename in replaced:
                    path = self.directory / filename
                    if original[filename] is None:
                        path.unlink()
                    else:
                        path.write_bytes(original[filename])
                raise
        finally:
            for path in prepared.values():
                path.unlink(missing_ok=True)


class StudentWindow:
    def __init__(self, root):
        self.root, self.store = root, StudentStore()
        self.records = {}
        root.title("จัดการข้อมูลนักศึกษา")
        apply_theme(root)
        window_size(root, 1060, 780, (940, 680))
        panel = ResponsivePanel(root, padding=28)
        panel.pack(fill="both", expand=True)
        page_header(panel, "ข้อมูลนักศึกษา", "ค้นหาและเลือกรายชื่อเพื่อแก้ไขข้อมูล • แสดงเฉพาะผู้ที่บันทึกใบหน้าแล้ว")
        bar = ttk.Frame(panel)
        bar.pack(fill="x", pady=8)
        ttk.Label(bar, text="ค้นหาชื่อ / รหัส").pack(side="left", padx=(0, 8))
        self.search = tk.StringVar()
        ttk.Entry(bar, textvariable=self.search).pack(side="left", fill="x", expand=True)
        ttk.Button(bar, text="โหลดรายชื่อใหม่", command=self.refresh).pack(side="right", padx=(8, 0))
        table = ttk.Frame(panel)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("number", "student_id", "name"), show="headings", selectmode="browse")
        for key, label, width in (("number", "ลำดับ", 60), ("student_id", "รหัสนักศึกษา", 180), ("name", "ชื่อ-นามสกุล", 370)):
            self.tree.heading(key, text=label)
            self.tree.column(key, width=width, minwidth=50)
        self.tree.pack(side="left", fill="both", expand=True)
        self.tree.tag_configure("alternate", background="#F5F9FB")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        scroll.pack(side="right", fill="y")
        self.tree.configure(yscrollcommand=scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self.select)
        editor = ttk.LabelFrame(panel, text="แก้ไขรายการที่เลือก", padding=12)
        editor.pack(fill="x", pady=12)
        self.student_id, self.name = tk.StringVar(), tk.StringVar()
        editor.columnconfigure(0, weight=1)
        editor.columnconfigure(1, weight=2)
        for col, (label, variable) in enumerate((("รหัสนักศึกษา", self.student_id), ("ชื่อ-นามสกุล", self.name))):
            ttk.Label(editor, text=label).grid(row=0, column=col, sticky="w", padx=(0, 12), pady=(0, 6))
            ttk.Entry(editor, textvariable=variable).grid(row=1, column=col, sticky="ew", padx=(0, 12))
        actions = ttk.Frame(panel)
        actions.pack(fill="x")
        self.edit_button = ttk.Button(actions, text="บันทึกการแก้ไข", command=self.edit, state="disabled", style="Primary.TButton")
        self.edit_button.pack(side="left")
        self.delete_button = ttk.Button(actions, text="ลบนักศึกษาและข้อมูลใบหน้า", command=self.delete, state="disabled", style="Danger.TButton")
        self.delete_button.pack(side="right")
        self.notice = tk.StringVar()
        ttk.Label(panel, textvariable=self.notice, style="Subtitle.TLabel").pack(anchor="w", pady=8)
        ttk.Label(panel, text="ชื่อและรหัสซิงก์กับหน้าเช็คชื่อด้วยมือ • ไม่แสดง Unknown", style="Subtitle.TLabel").pack(anchor="w")
        responsive_row(actions, minimum=260)
        table_scrollbars(table, self.tree)
        wrap_labels(panel)
        self.search.trace_add("write", lambda *_: self.render())
        self.refresh()

    def refresh(self):
        try:
            rows = self.store.rows()
        except Exception as exc:
            messagebox.showerror("โหลดรายชื่อไม่ได้", str(exc), parent=self.root)
            rows = []
        self.records = {str(i): row for i, row in enumerate(rows)}
        self.render()

    def render(self):
        self.tree.delete(*self.tree.get_children())
        query = self.search.get().strip().casefold()
        count = 0
        for key, row in self.records.items():
            if query in row["name"].casefold() or query in str(row["stu_id"]).casefold():
                count += 1
                self.tree.insert("", "end", iid=key, values=(count, str(row["stu_id"]), row["name"]), tags=("alternate",) if count % 2 == 0 else ())
        self.select()
        self.notice.set(f"แสดง {count} จาก {len(self.records)} คน · เลือกแถวเพื่อแก้ไขข้อมูล" if count else "ไม่พบรายชื่อ · ลองเปลี่ยนคำค้นหาหรือลงทะเบียนใบหน้าใหม่")

    def select(self, event=None):
        selected = self.tree.selection()
        row = self.records.get(selected[0]) if selected else None
        self.name.set(row["name"] if row else "")
        self.student_id.set(str(row["stu_id"]) if row else "")
        for button in (self.edit_button, self.delete_button):
            button.configure(state="normal" if row else "disabled")

    def change(self, delete=False):
        selected = self.tree.selection()
        if not selected:
            return
        row = self.records[selected[0]]
        if delete and not messagebox.askyesno("ยืนยันการลบ", f"ลบ {row['name']} (รหัส {row['stu_id']})\nพร้อมตัวอย่างใบหน้าทั้งหมดของนักศึกษาคนนี้หรือไม่?", parent=self.root):
            return
        try:
            self.store.change(row, **({} if delete else {"name": self.name.get(), "student_id": self.student_id.get()}))
        except Exception as exc:
            messagebox.showerror("บันทึกไม่สำเร็จ", str(exc), parent=self.root)
            return
        self.refresh()
        self.notice.set("ลบข้อมูลแล้ว" if delete else "บันทึกการแก้ไขแล้ว")

    def edit(self):
        self.change()

    def delete(self):
        self.change(delete=True)


def main():
    root = tk.Tk()
    StudentWindow(root)
    root.mainloop()


if __name__ == "__main__":
    main()
