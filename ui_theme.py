"""Shared presentation styles for the attendance desktop application."""
import tkinter as tk
import tkinter.font as tkfont
from tkinter import ttk

BG = "#F3F6F8"
SURFACE = "#FFFFFF"
INK = "#172B3A"
MUTED = "#536877"
BORDER = "#D9E3E8"
PRIMARY = "#087E83"
SUCCESS_BG = "#E8F5EF"
SUCCESS_FG = "#176444"
WARNING_BG = "#FFF3DB"
WARNING_FG = "#895400"
DANGER = "#B43E46"


def apply_theme(root):
    families = set(tkfont.families(root))
    family = next((name for name in ("Thonburi", "Noto Sans Thai", "Leelawadee UI", "Tahoma") if name in families), "Helvetica")
    root.configure(background=BG)
    root.option_add("*Font", (family, 11))
    root.option_add("*selectBackground", "#D5EEEF")
    root.option_add("*selectForeground", INK)
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", font=(family, 11), background=BG, foreground=INK)
    style.configure("TFrame", background=BG)
    style.configure("Card.TFrame", background=SURFACE, borderwidth=1, relief="solid", bordercolor=BORDER)
    style.configure("TLabel", background=BG, foreground=INK)
    style.configure("Title.TLabel", font=(family, 23, "bold"))
    style.configure("Subtitle.TLabel", foreground=MUTED)
    style.configure("Eyebrow.TLabel", foreground=PRIMARY, font=(family, 10, "bold"))
    style.configure("Section.TLabel", font=(family, 12, "bold"))
    style.configure("Card.TLabel", background=SURFACE)
    style.configure("CardTitle.TLabel", background=SURFACE, font=(family, 16, "bold"))
    style.configure("CardNote.TLabel", background=SURFACE, foreground=MUTED)
    style.configure("Number.TLabel", background=SURFACE, foreground=PRIMARY, font=(family, 24, "bold"))
    style.configure("Summary.TLabel", background="#E4EFF1", foreground="#215C63", padding=(14, 10), font=(family, 11, "bold"))
    style.configure("TButton", padding=(15, 10), background=SURFACE, foreground=INK,
                    borderwidth=1, bordercolor=BORDER, focusthickness=2, focuscolor=PRIMARY)
    style.map("TButton", background=[("disabled", "#E9EEF1"), ("pressed", "#D5E7E9"), ("active", "#EAF2F4")],
              foreground=[("disabled", "#84959F")], bordercolor=[("focus", PRIMARY)])
    for name, color, hover in (("Primary", PRIMARY, "#06686D"), ("Success", SUCCESS_FG, "#104E34")):
        style.configure(f"{name}.TButton", background=color, foreground=SURFACE, bordercolor=color)
        style.map(f"{name}.TButton", background=[("disabled", "#DEE8EA"), ("pressed", hover), ("active", hover)],
                  foreground=[("disabled", "#758892"), ("!disabled", SURFACE)])
    for name, color, background in (("Danger", DANGER, "#FCECEF"), ("Warning", WARNING_FG, WARNING_BG)):
        style.configure(f"{name}.TButton", foreground=color, background=background, bordercolor=background)
        style.map(f"{name}.TButton", foreground=[("disabled", "#84959F"), ("!disabled", color)],
                  background=[("disabled", "#E9EEF1"), ("active", "#F2E2D7")])
    style.configure("TEntry", fieldbackground=SURFACE, foreground=INK, bordercolor=BORDER,
                    padding=(10, 9), insertcolor=INK, lightcolor=BORDER, darkcolor=BORDER)
    style.map("TEntry", bordercolor=[("focus", PRIMARY)], lightcolor=[("focus", PRIMARY)])
    style.configure("TCheckbutton", background=BG, padding=(0, 6))
    style.map("TCheckbutton", background=[("active", BG)], indicatorbackground=[("selected", PRIMARY)])
    style.configure("TLabelframe", background=BG, bordercolor=BORDER, borderwidth=1, relief="solid")
    style.configure("TLabelframe.Label", foreground=MUTED, font=(family, 10, "bold"), background=BG)
    style.configure("Treeview", background=SURFACE, fieldbackground=SURFACE, foreground=INK,
                    borderwidth=0, rowheight=38, font=(family, 11))
    style.configure("Treeview.Heading", background="#E8EFF3", foreground=MUTED,
                    padding=(10, 12), font=(family, 10, "bold"), relief="flat")
    style.map("Treeview", background=[("selected", "#D5EEEF")], foreground=[("selected", "#103E43")])
    style.map("Treeview.Heading", background=[("active", "#DFE9EE")])
    style.configure("Vertical.TScrollbar", background="#BCCDD5", troughcolor=BG, borderwidth=0, arrowsize=12)
    root._ui_font = family
    return family


def window_size(root, width, height, minimum=(600, 420)):
    max_width = max(400, root.winfo_screenwidth() - 80)
    max_height = max(350, root.winfo_screenheight() - 110)
    width, height = min(width, max_width), min(height, max_height)
    root.resizable(True, True)
    root.minsize(min(420, width), min(320, height))
    root.geometry(f"{width}x{height}+{max(0, (root.winfo_screenwidth()-width)//2)}+{max(0, (root.winfo_screenheight()-height)//2-20)}")


def page_header(parent, title, description, eyebrow="ระบบเช็คชื่อนักศึกษา"):
    header = ttk.Frame(parent)
    header.pack(fill="x", pady=(0, 20))
    ttk.Label(header, text=eyebrow, style="Eyebrow.TLabel").pack(anchor="w", pady=(0, 5))
    title_label = ttk.Label(header, text=title, style="Title.TLabel", wraplength=600)
    title_label.pack(anchor="w", fill="x")
    subtitle = ttk.Label(header, text=description, style="Subtitle.TLabel", wraplength=800)
    subtitle.pack(anchor="w", pady=(6, 0), fill="x")
    def resize(event):
        for label in (title_label, subtitle):
            label.configure(wraplength=max(80, event.width))
    header.bind("<Configure>", resize, add="+")


class ResponsivePanel(ttk.Frame):
    """A form that fills its viewport and scrolls when its content cannot fit.

    The public frame remains the parent of existing widgets, so modal ownership,
    callbacks and pack/grid layouts do not change.
    """
    def __init__(self, parent, padding=24):
        self.shell = ttk.Frame(parent)
        self.canvas = tk.Canvas(self.shell, background=BG, highlightthickness=0,
                                width=1, height=1)
        self.vertical = ttk.Scrollbar(self.shell, orient="vertical", command=self.canvas.yview)
        self.horizontal = ttk.Scrollbar(self.shell, orient="horizontal", command=self.canvas.xview)
        self.shell.columnconfigure(0, weight=1)
        self.shell.rowconfigure(0, weight=1)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vertical.grid(row=0, column=1, sticky="ns")
        self.horizontal.grid(row=1, column=0, sticky="ew")
        self.canvas.configure(yscrollcommand=self.vertical.set, xscrollcommand=self.horizontal.set)
        super().__init__(self.canvas, padding=padding)
        self.item = self.canvas.create_window(0, 0, window=self, anchor="nw")
        self._viewport_size = None
        self.canvas.bind("<Configure>", self._resize)
        self.bind("<Configure>", self._resize)

    def pack(self, **kwargs):
        self.shell.pack(**kwargs)

    def _resize(self, event=None):
        width = max(360, self.canvas.winfo_width())
        height = max(self.canvas.winfo_height(), self.winfo_reqheight())
        if self._viewport_size == (width, height):
            return
        self._viewport_size = (width, height)
        self.canvas.itemconfigure(self.item, width=width, height=height)
        self.canvas.configure(scrollregion=(0, 0, width, height))



def responsive_row(parent, widgets=None, minimum=180, max_columns=None):
    """Reflow a row into as many equally sized columns as the window allows."""
    widgets = list(widgets if widgets is not None else parent.winfo_children())
    for widget in widgets:
        widget.pack_forget()
    previous = [None]
    def layout(event=None):
        columns = max(1, min(len(widgets), max(1, parent.winfo_width()) // minimum))
        if max_columns is not None:
            columns = min(columns, max_columns)
        if columns == previous[0]:
            return
        previous[0] = columns
        for index in range(len(widgets)):
            parent.columnconfigure(index, weight=1 if index < columns else 0,
                                   uniform="responsive" if index < columns else "", minsize=0)
            parent.rowconfigure(index, weight=1 if index < (len(widgets) + columns - 1) // columns else 0,
                                uniform="", minsize=0)
        for index, widget in enumerate(widgets):
            widget.grid(row=index // columns, column=index % columns, sticky="nsew", padx=4, pady=4)
    parent.bind("<Configure>", layout, add="+")
    layout()


def wrap_labels(parent):
    """Wrap prose at its actual allocated width, including variable status text."""
    for widget in parent.winfo_children():
        if isinstance(widget, ttk.Entry):
            if widget.winfo_manager() == "pack":
                widget.pack_configure(fill="x", expand=widget.pack_info().get("side") in ("left", "right"))
        elif isinstance(widget, ttk.Label):
            if widget.cget("image"):
                continue
            widget.configure(wraplength=240)
            if widget.winfo_manager() == "pack" and widget.pack_info().get("side") == "top":
                widget.pack_configure(fill="x")
            def resize_text(event, label=widget):
                columns = max((int(child.grid_info()["column"]) + 1
                               for child in label.master.winfo_children()
                               if child.winfo_manager() == "grid"), default=1) if label.winfo_manager() == "grid" else 1
                width = max(60, event.width // columns - 24)
                if int(label.cget("wraplength")) != width:
                    label.configure(wraplength=width)
            widget.master.bind("<Configure>", resize_text, add="+")
        elif isinstance(widget, ttk.Button):
            original = widget.cget("text")
            def resize_button(event, button=widget, text=original):
                font = tkfont.Font(font=ttk.Style(button).lookup(button.cget("style") or "TButton", "font"))
                columns = max((int(child.grid_info()["column"]) + 1
                               for child in button.master.winfo_children()
                               if child.winfo_manager() == "grid"), default=1) if button.winfo_manager() == "grid" else 1
                limit = max(60, event.width // columns - 72)
                lines, line = [], ""
                for char in text:
                    if char == "\n" or (line and font.measure(line + char) > limit):
                        lines.append(line)
                        line = "" if char == "\n" else char
                    else:
                        line += char
                lines.append(line)
                value = "\n".join(lines)
                if button.cget("text") != value:
                    button.configure(text=value)
            widget.master.bind("<Configure>", resize_button, add="+")
        else:
            wrap_labels(widget)


def table_scrollbars(table, tree):
    """Keep all columns reachable on a narrow window."""
    for widget in table.winfo_children():
        if widget is not tree:
            widget.destroy()
    tree.pack_forget()
    tree.configure(height=5)
    table.columnconfigure(0, weight=1)
    table.rowconfigure(0, weight=1)
    tree.grid(row=0, column=0, sticky="nsew")
    vertical = ttk.Scrollbar(table, orient="vertical", command=tree.yview)
    horizontal = ttk.Scrollbar(table, orient="horizontal", command=tree.xview)
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    tree.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)


def fit_image_size(image_size, available):
    scale = min(available[0] / image_size[0], available[1] / image_size[1])
    return tuple(max(1, int(dimension * scale)) for dimension in image_size)


def status_table(tree):
    tree.tag_configure("ขาดเรียน", background="#FCECEF", foreground=DANGER)
    for status in ("มา", "ตรงเวลา"):
        tree.tag_configure(status, background=SUCCESS_BG, foreground=SUCCESS_FG)
    tree.tag_configure("มาสาย", background=WARNING_BG, foreground=WARNING_FG)
    tree.tag_configure("ยังไม่เช็ค", foreground=MUTED)
