"""
gui.py
------
Main GUI module for the Advanced PDF Text Extractor and Merger System.

Architecture:
  - PDFConverterApp  : Root application class, owns all state and widgets
  - FileListPanel    : Left-side panel for file management
  - ControlPanel     : Centre-right panel of action buttons
  - OutputPanel      : Text & status output area
  - MetadataDialog   : Popup window for PDF metadata

All long-running operations are dispatched to a background thread so the
Tkinter event loop is never blocked.
"""

import os
import sys
import threading
import re
from tkinter import (
    Tk, Frame, Label, Button, Text, Entry, Scrollbar, Listbox,
    StringVar, IntVar, BooleanVar, messagebox, filedialog,
    ttk, END, BOTH, LEFT, RIGHT, TOP, BOTTOM, X, Y, WORD,
    HORIZONTAL, VERTICAL, NW, W, E, N, S, NSEW, EW, RIDGE,
    PhotoImage, Canvas, Menu
)
from tkinter.font import Font

# ── Project modules ───────────────────────────────────────────────────────────
import pdf_utils
import ocr_utils
import word_utils


# ═════════════════════════════════════════════════════════════════════════════
#  THEME CONSTANTS
#  A dark, modern colour palette reminiscent of VS-Code Dark+
# ═════════════════════════════════════════════════════════════════════════════
THEME = {
    # Backgrounds
    "bg_root"       : "#1e1e2e",   # Dark navy – main window
    "bg_sidebar"    : "#181825",   # Darker – file list
    "bg_panel"      : "#24273a",   # Slightly lighter – control panel
    "bg_output"     : "#1e1e2e",   # Output text area
    "bg_input"      : "#2a2a3e",   # Input fields
    "bg_listbox"    : "#21213a",   # File listbox

    # Foregrounds
    "fg_primary"    : "#cdd6f4",   # Off-white – primary text
    "fg_secondary"  : "#a6adc8",   # Muted – secondary text
    "fg_accent"     : "#89b4fa",   # Blue accent
    "fg_success"    : "#a6e3a1",   # Green
    "fg_error"      : "#f38ba8",   # Red / Pink
    "fg_warning"    : "#f9e2af",   # Yellow
    "fg_keyword"    : "#fab387",   # Orange – highlighted keywords

    # Button styles
    "btn_primary"   : "#6c5ce7",   # Purple primary
    "btn_primary_h" : "#7c6cf0",   # Hover purple
    "btn_success"   : "#00b894",   # Green (extract / save)
    "btn_success_h" : "#00cba3",
    "btn_danger"    : "#e17055",   # Orange (clear)
    "btn_danger_h"  : "#f08c6e",
    "btn_info"      : "#0984e3",   # Blue (search)
    "btn_info_h"    : "#2196f3",
    "btn_ocr"       : "#6d28d9",   # Violet (OCR)
    "btn_ocr_h"     : "#7c3aed",
    "btn_merge"     : "#d63031",   # Red (merge)
    "btn_merge_h"   : "#e84393",

    # Borders & misc
    "border"        : "#313244",
    "progress_trough": "#313244",
    "progress_bar"  : "#89b4fa",
    "separator"     : "#45475a",
}

FONT_FAMILY = "Segoe UI"

# ═════════════════════════════════════════════════════════════════════════════
#  HELPER: THREADED TASK RUNNER
# ═════════════════════════════════════════════════════════════════════════════

def run_in_thread(fn):
    """Decorator that runs `fn` in a daemon thread (prevents UI freezing)."""
    def wrapper(*args, **kwargs):
        t = threading.Thread(target=fn, args=args, kwargs=kwargs, daemon=True)
        t.start()
    return wrapper


# ═════════════════════════════════════════════════════════════════════════════
#  MAIN APPLICATION CLASS
# ═════════════════════════════════════════════════════════════════════════════

class PDFConverterApp:
    """Root application controller."""

    def __init__(self, root: Tk):
        self.root = root
        self._setup_window()
        self._setup_fonts()
        self._build_menu()
        self._build_layout()
        self._configure_styles()

        # ── State ─────────────────────────────────────────────────────────────
        self.loaded_files: list[str] = []        # Absolute paths of loaded PDFs
        self._op_lock = threading.Lock()          # Prevent concurrent operations

    # ─────────────────────────────────────────────────────────────────────────
    #  WINDOW CONFIG
    # ─────────────────────────────────────────────────────────────────────────

    def _setup_window(self):
        self.root.title("Advanced PDF Text Extractor & Merger")
        self.root.geometry("1280x780")
        self.root.minsize(1000, 640)
        self.root.configure(bg=THEME["bg_root"])

        # Center on screen
        self.root.update_idletasks()
        w, h = 1280, 780
        x = (self.root.winfo_screenwidth()  - w) // 2
        y = (self.root.winfo_screenheight() - h) // 2
        self.root.geometry(f"{w}x{h}+{x}+{y}")

    def _setup_fonts(self):
        self.font_title   = Font(family=FONT_FAMILY, size=13, weight="bold")
        self.font_heading  = Font(family=FONT_FAMILY, size=10, weight="bold")
        self.font_body     = Font(family=FONT_FAMILY, size=10)
        self.font_mono     = Font(family="Consolas",   size=10)
        self.font_small    = Font(family=FONT_FAMILY, size=9)
        self.font_btn      = Font(family=FONT_FAMILY, size=10, weight="bold")

    # ─────────────────────────────────────────────────────────────────────────
    #  MENU BAR
    # ─────────────────────────────────────────────────────────────────────────

    def _build_menu(self):
        menubar = Menu(self.root, bg=THEME["bg_panel"],
                       fg=THEME["fg_primary"], activebackground=THEME["btn_primary"],
                       activeforeground="white", relief="flat", tearoff=False)

        # File menu
        file_menu = Menu(menubar, tearoff=False, bg=THEME["bg_panel"],
                         fg=THEME["fg_primary"], activebackground=THEME["btn_primary"],
                         activeforeground="white")
        file_menu.add_command(label="📂  Open File(s)…",    command=self.upload_pdfs)
        file_menu.add_command(label="💾  Save Extracted Text…", command=self.save_text)
        file_menu.add_separator()
        file_menu.add_command(label="🗑  Clear All",        command=self.clear_all)
        file_menu.add_separator()
        file_menu.add_command(label="Exit",                 command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)

        # Help menu
        help_menu = Menu(menubar, tearoff=False, bg=THEME["bg_panel"],
                         fg=THEME["fg_primary"], activebackground=THEME["btn_primary"],
                         activeforeground="white")
        help_menu.add_command(label="About", command=self._show_about)
        menubar.add_cascade(label="Help", menu=help_menu)

        self.root.config(menu=menubar)

    # ─────────────────────────────────────────────────────────────────────────
    #  LAYOUT BUILDER
    # ─────────────────────────────────────────────────────────────────────────

    def _build_layout(self):
        # ── Title bar ─────────────────────────────────────────────────────────
        title_bar = Frame(self.root, bg=THEME["bg_sidebar"], height=54)
        title_bar.pack(side=TOP, fill=X)
        title_bar.pack_propagate(False)

        Label(
            title_bar,
            text="🗂  Advanced PDF Text Extractor & Merger",
            font=self.font_title,
            bg=THEME["bg_sidebar"],
            fg=THEME["fg_accent"],
            padx=18,
        ).pack(side=LEFT, pady=10)

        Label(
            title_bar,
            text="v1.0  •  Built with Python + Tkinter",
            font=self.font_small,
            bg=THEME["bg_sidebar"],
            fg=THEME["fg_secondary"],
            padx=18,
        ).pack(side=RIGHT, pady=10)

        # ── Main content (sidebar | main area) ───────────────────────────────
        content = Frame(self.root, bg=THEME["bg_root"])
        content.pack(fill=BOTH, expand=True)

        self._build_sidebar(content)
        self._build_main_area(content)

        # ── Status bar at bottom ──────────────────────────────────────────────
        self._build_status_bar()

    def _build_sidebar(self, parent):
        """Left panel: file list + file action buttons."""
        sidebar = Frame(parent, bg=THEME["bg_sidebar"], width=290)
        sidebar.pack(side=LEFT, fill=Y, padx=(0, 0))
        sidebar.pack_propagate(False)

        # Section label
        Label(sidebar, text="📁  Loaded Files",
              font=self.font_heading, bg=THEME["bg_sidebar"],
              fg=THEME["fg_accent"], pady=10, padx=12).pack(anchor=W)

        # ── File count badge ──────────────────────────────────────────────────
        self.file_count_var = StringVar(value="No files loaded")
        Label(sidebar, textvariable=self.file_count_var,
              font=self.font_small, bg=THEME["bg_sidebar"],
              fg=THEME["fg_secondary"], padx=12).pack(anchor=W, pady=(0, 6))

        # ── Listbox + scrollbar ───────────────────────────────────────────────
        list_frame = Frame(sidebar, bg=THEME["bg_sidebar"])
        list_frame.pack(fill=BOTH, expand=True, padx=10, pady=(0, 8))

        sb = Scrollbar(list_frame, orient=VERTICAL,
                       bg=THEME["bg_sidebar"], troughcolor=THEME["bg_root"])
        sb.pack(side=RIGHT, fill=Y)

        self.file_listbox = Listbox(
            list_frame,
            yscrollcommand=sb.set,
            bg=THEME["bg_listbox"],
            fg=THEME["fg_primary"],
            selectbackground=THEME["btn_primary"],
            selectforeground="white",
            font=self.font_small,
            activestyle="none",
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightcolor=THEME["border"],
            highlightbackground=THEME["border"],
        )
        self.file_listbox.pack(side=LEFT, fill=BOTH, expand=True)
        sb.config(command=self.file_listbox.yview)

        # Double-click to view metadata
        self.file_listbox.bind("<Double-Button-1>", lambda e: self.show_metadata())

        # ── Sidebar buttons ───────────────────────────────────────────────────
        btn_frame = Frame(sidebar, bg=THEME["bg_sidebar"])
        btn_frame.pack(fill=X, padx=10, pady=(0, 12))

        self._make_button(btn_frame, "📂  Upload File(s)", self.upload_pdfs,
                          THEME["btn_primary"], THEME["btn_primary_h"]).pack(fill=X, pady=3)
        self._make_button(btn_frame, "ℹ  View Metadata", self.show_metadata,
                          THEME["btn_info"], THEME["btn_info_h"]).pack(fill=X, pady=3)
        self._make_button(btn_frame, "❌  Remove Selected", self.remove_selected_file,
                          THEME["btn_danger"], THEME["btn_danger_h"]).pack(fill=X, pady=3)
        self._make_button(btn_frame, "🗑  Clear All Files", self.clear_all,
                          THEME["btn_danger"], THEME["btn_danger_h"]).pack(fill=X, pady=3)

        # ── Page range input ──────────────────────────────────────────────────
        Label(sidebar, text="📄  Page Range (e.g. 1-3, 5, 7-9)",
              font=self.font_small, bg=THEME["bg_sidebar"],
              fg=THEME["fg_secondary"], padx=12).pack(anchor=W, pady=(6, 2))

        self.page_range_var = StringVar()
        page_entry = Entry(
            sidebar,
            textvariable=self.page_range_var,
            font=self.font_body,
            bg=THEME["bg_input"],
            fg=THEME["fg_primary"],
            insertbackground=THEME["fg_accent"],
            relief="flat",
            bd=6,
            highlightthickness=1,
            highlightcolor=THEME["btn_primary"],
            highlightbackground=THEME["border"],
        )
        page_entry.pack(fill=X, padx=10, pady=(0, 4))

        # ── Merge output path ─────────────────────────────────────────────────
        Label(sidebar, text="📦  Merge Output Filename",
              font=self.font_small, bg=THEME["bg_sidebar"],
              fg=THEME["fg_secondary"], padx=12).pack(anchor=W, pady=(4, 2))

        self.merge_output_var = StringVar(value="merged_output.pdf")
        merge_entry = Entry(
            sidebar,
            textvariable=self.merge_output_var,
            font=self.font_body,
            bg=THEME["bg_input"],
            fg=THEME["fg_primary"],
            insertbackground=THEME["fg_accent"],
            relief="flat",
            bd=6,
            highlightthickness=1,
            highlightcolor=THEME["btn_primary"],
            highlightbackground=THEME["border"],
        )
        merge_entry.pack(fill=X, padx=10, pady=(0, 10))

    def _build_main_area(self, parent):
        """Right panel: action buttons + output text box."""
        main = Frame(parent, bg=THEME["bg_root"])
        main.pack(side=LEFT, fill=BOTH, expand=True)

        # ── Action buttons row ────────────────────────────────────────────────
        btn_row = Frame(main, bg=THEME["bg_panel"], pady=12)
        btn_row.pack(fill=X, padx=10, pady=(10, 4))

        actions = [
            ("📝  Extract Text",  self.extract_text,  THEME["btn_success"], THEME["btn_success_h"]),
            ("🔀  Merge PDFs",    self.merge_pdfs,    THEME["btn_merge"],   THEME["btn_merge_h"]),
            ("🔍  Search Keyword",self.search_keyword, THEME["btn_info"],    THEME["btn_info_h"]),
            ("🔬  Apply OCR",     self.apply_ocr,     THEME["btn_ocr"],     THEME["btn_ocr_h"]),
            ("💾  Save Text",     self.save_text,     THEME["btn_primary"], THEME["btn_primary_h"]),
        ]

        for label, cmd, bg, hover in actions:
            self._make_button(btn_row, label, cmd, bg, hover,
                              padx=10, pady=6).pack(side=LEFT, padx=6)

        # ── Word Utilities row ────────────────────────────────────────────────
        word_row = Frame(main, bg=THEME["bg_panel"], pady=12)
        word_row.pack(fill=X, padx=10, pady=(0, 4))

        actions_word = [
            ("📄  PDF to Word",   self.run_pdf_to_word, THEME["btn_ocr"],     THEME["btn_ocr_h"]),
            ("📝  Word to PDF",   self.run_word_to_pdf, THEME["btn_ocr"],     THEME["btn_ocr_h"]),
            ("🗂  Merge Word",    self.run_merge_word,  THEME["btn_merge"],   THEME["btn_merge_h"]),
        ]

        for label, cmd, bg, hover in actions_word:
            self._make_button(word_row, label, cmd, bg, hover,
                              padx=10, pady=6).pack(side=LEFT, padx=6)

        # ── Search bar ────────────────────────────────────────────────────────
        search_row = Frame(main, bg=THEME["bg_root"])
        search_row.pack(fill=X, padx=10, pady=(0, 4))

        Label(search_row, text="🔍 Keyword:",
              font=self.font_body, bg=THEME["bg_root"],
              fg=THEME["fg_secondary"]).pack(side=LEFT, padx=(4, 6))

        self.keyword_var = StringVar()
        kw_entry = Entry(
            search_row,
            textvariable=self.keyword_var,
            font=self.font_body,
            bg=THEME["bg_input"],
            fg=THEME["fg_primary"],
            insertbackground=THEME["fg_accent"],
            relief="flat",
            bd=6,
            highlightthickness=1,
            highlightcolor=THEME["btn_info"],
            highlightbackground=THEME["border"],
            width=28,
        )
        kw_entry.pack(side=LEFT, padx=(0, 8))
        kw_entry.bind("<Return>", lambda e: self.search_keyword())

        # Case-sensitive toggle
        self.case_sensitive_var = BooleanVar(value=False)
        ttk.Checkbutton(
            search_row,
            text="Case-sensitive",
            variable=self.case_sensitive_var,
            style="Dark.TCheckbutton",
        ).pack(side=LEFT, padx=4)

        # OCR language
        Label(search_row, text="  OCR Lang:",
              font=self.font_body, bg=THEME["bg_root"],
              fg=THEME["fg_secondary"]).pack(side=LEFT, padx=(12, 4))

        self.ocr_lang_var = StringVar(value="eng")
        lang_entry = Entry(
            search_row,
            textvariable=self.ocr_lang_var,
            font=self.font_body,
            bg=THEME["bg_input"],
            fg=THEME["fg_primary"],
            insertbackground=THEME["fg_accent"],
            relief="flat",
            bd=6,
            highlightthickness=1,
            highlightcolor=THEME["btn_ocr"],
            highlightbackground=THEME["border"],
            width=6,
        )
        lang_entry.pack(side=LEFT)

        # ── Output text area ──────────────────────────────────────────────────
        output_frame = Frame(main, bg=THEME["bg_root"])
        output_frame.pack(fill=BOTH, expand=True, padx=10, pady=(4, 0))

        Label(output_frame, text="📋  Output",
              font=self.font_heading, bg=THEME["bg_root"],
              fg=THEME["fg_accent"]).pack(anchor=W, pady=(0, 4))

        # Scrolled text widget
        text_scroll_y = Scrollbar(output_frame, orient=VERTICAL,
                                  bg=THEME["bg_root"], troughcolor=THEME["bg_root"])
        text_scroll_y.pack(side=RIGHT, fill=Y)

        text_scroll_x = Scrollbar(output_frame, orient=HORIZONTAL,
                                  bg=THEME["bg_root"], troughcolor=THEME["bg_root"])
        text_scroll_x.pack(side=BOTTOM, fill=X)

        self.output_text = Text(
            output_frame,
            yscrollcommand=text_scroll_y.set,
            xscrollcommand=text_scroll_x.set,
            wrap=WORD,
            bg=THEME["bg_output"],
            fg=THEME["fg_primary"],
            insertbackground=THEME["fg_accent"],
            selectbackground=THEME["btn_primary"],
            selectforeground="white",
            font=self.font_mono,
            relief="flat",
            bd=0,
            highlightthickness=1,
            highlightcolor=THEME["border"],
            highlightbackground=THEME["border"],
            state="disabled",
            padx=10,
            pady=10,
        )
        self.output_text.pack(side=LEFT, fill=BOTH, expand=True)

        text_scroll_y.config(command=self.output_text.yview)
        text_scroll_x.config(command=self.output_text.xview)

        # Tags for coloured text in output
        self.output_text.tag_config("success", foreground=THEME["fg_success"])
        self.output_text.tag_config("error",   foreground=THEME["fg_error"])
        self.output_text.tag_config("warning", foreground=THEME["fg_warning"])
        self.output_text.tag_config("heading", foreground=THEME["fg_accent"],
                                    font=self.font_heading)
        self.output_text.tag_config("keyword", background=THEME["fg_keyword"],
                                    foreground=THEME["bg_root"])

    def _build_status_bar(self):
        """Bottom bar: status label + progress bar."""
        status_bar = Frame(self.root, bg=THEME["bg_sidebar"], height=36)
        status_bar.pack(side=BOTTOM, fill=X)
        status_bar.pack_propagate(False)

        self.status_var = StringVar(value="Ready  •  Load PDF files to begin")
        status_lbl = Label(
            status_bar,
            textvariable=self.status_var,
            font=self.font_small,
            bg=THEME["bg_sidebar"],
            fg=THEME["fg_secondary"],
            anchor=W,
            padx=14,
        )
        status_lbl.pack(side=LEFT, fill=Y)

        # Progress bar
        self.progress_var = IntVar(value=0)
        self.progress = ttk.Progressbar(
            status_bar,
            variable=self.progress_var,
            maximum=100,
            style="Blue.Horizontal.TProgressbar",
            length=260,
        )
        self.progress.pack(side=RIGHT, padx=14, pady=8)

    def _configure_styles(self):
        """Configure ttk styles to match dark theme."""
        style = ttk.Style()
        style.theme_use("clam")

        # Progress bar
        style.configure(
            "Blue.Horizontal.TProgressbar",
            troughcolor=THEME["progress_trough"],
            background=THEME["progress_bar"],
            bordercolor=THEME["border"],
            lightcolor=THEME["progress_bar"],
            darkcolor=THEME["progress_bar"],
        )

        # Checkbutton
        style.configure(
            "Dark.TCheckbutton",
            background=THEME["bg_root"],
            foreground=THEME["fg_secondary"],
            focuscolor="none",
        )
        style.map("Dark.TCheckbutton",
                  foreground=[("active", THEME["fg_accent"])],
                  background=[("active", THEME["bg_root"])])

    # ─────────────────────────────────────────────────────────────────────────
    #  BUTTON FACTORY
    # ─────────────────────────────────────────────────────────────────────────

    def _make_button(self, parent, text, command, bg_color, hover_color,
                     padx=14, pady=8):
        """Create a flat, hover-animated button with the project colour scheme."""
        btn = Button(
            parent,
            text=text,
            command=command,
            font=self.font_btn,
            bg=bg_color,
            fg="white",
            activebackground=hover_color,
            activeforeground="white",
            relief="flat",
            bd=0,
            padx=padx,
            pady=pady,
            cursor="hand2",
        )
        # Hover animation
        btn.bind("<Enter>", lambda e, b=btn, c=hover_color: b.config(bg=c))
        btn.bind("<Leave>", lambda e, b=btn, c=bg_color:   b.config(bg=c))
        return btn

    # ─────────────────────────────────────────────────────────────────────────
    #  STATUS / OUTPUT HELPERS
    # ─────────────────────────────────────────────────────────────────────────

    def _set_status(self, message: str, tag: str = ""):
        """Update the bottom status bar (thread-safe via after())."""
        self.root.after(0, lambda: self.status_var.set(message))

    def _write_output(self, text: str, tag: str = ""):
        """Append text to the output box (thread-safe)."""
        def _do_write():
            self.output_text.config(state="normal")
            self.output_text.insert(END, text + "\n", tag if tag else "")
            self.output_text.see(END)
            self.output_text.config(state="disabled")
        self.root.after(0, _do_write)

    def _clear_output(self):
        """Clear the output text box (thread-safe)."""
        def _do_clear():
            self.output_text.config(state="normal")
            self.output_text.delete("1.0", END)
            self.output_text.config(state="disabled")
        self.root.after(0, _do_clear)

    def _set_progress(self, value: int):
        """Update the progress bar (thread-safe, 0-100)."""
        self.root.after(0, lambda: self.progress_var.set(value))

    def _reset_progress(self):
        self._set_progress(0)

    def _update_file_count(self):
        """Update the file count badge above the listbox."""
        n = len(self.loaded_files)
        text = f"{n} file{'s' if n != 1 else ''} loaded" if n else "No files loaded"
        self.root.after(0, lambda: self.file_count_var.set(text))

    # ─────────────────────────────────────────────────────────────────────────
    #  FILE MANAGEMENT
    # ─────────────────────────────────────────────────────────────────────────

    def upload_pdfs(self):
        """Open a file dialog and load PDF/Word files into the list."""
        paths = filedialog.askopenfilenames(
            title="Select File(s)",
            filetypes=[("Supported Files", "*.pdf;*.docx"), ("PDF Files", "*.pdf"), ("Word Files", "*.docx"), ("All Files", "*.*")],
        )
        if not paths:
            return

        added = 0
        for path in paths:
            if path not in self.loaded_files:
                self.loaded_files.append(path)
                short_name = os.path.basename(path)
                self.file_listbox.insert(END, f"  {short_name}")
                added += 1

        self._update_file_count()
        self._set_status(f"✅  Loaded {added} new file(s)  •  Total: {len(self.loaded_files)}")

    def remove_selected_file(self):
        """Remove the currently selected file from the list."""
        sel = self.file_listbox.curselection()
        if not sel:
            messagebox.showwarning("No Selection", "Please select a file to remove.")
            return
        idx = sel[0]
        self.file_listbox.delete(idx)
        removed = self.loaded_files.pop(idx)
        self._update_file_count()
        self._set_status(f"🗑  Removed: {os.path.basename(removed)}")

    def clear_all(self):
        """Clear all loaded files and the output box."""
        self.loaded_files.clear()
        self.file_listbox.delete(0, END)
        self._clear_output()
        self._set_status("🗑  All files cleared")
        self._update_file_count()
        self._reset_progress()

    # ─────────────────────────────────────────────────────────────────────────
    #  METADATA VIEWER
    # ─────────────────────────────────────────────────────────────────────────

    def show_metadata(self):
        """Show metadata for the selected (or first) file."""
        sel = self.file_listbox.curselection()
        if not sel and not self.loaded_files:
            messagebox.showwarning("No File", "Load a file first.")
            return
        idx = sel[0] if sel else 0
        file_path = self.loaded_files[idx]

        try:
            if file_path.lower().endswith(".docx"):
                meta = word_utils.get_word_metadata(file_path)
            else:
                meta = pdf_utils.get_pdf_metadata(file_path)
        except Exception as ex:
            messagebox.showerror("Error", str(ex))
            return

        self._clear_output()
        self._write_output("═" * 56, "heading")
        self._write_output("  PDF METADATA", "heading")
        self._write_output("═" * 56, "heading")
        for key, val in meta.items():
            label = key.replace("_", " ").title().ljust(14)
            self._write_output(f"  {label}: {val}")
        self._write_output("═" * 56, "heading")
        self._set_status(f"ℹ  Showing metadata for: {meta['file_name']}")

    # ─────────────────────────────────────────────────────────────────────────
    #  TEXT EXTRACTION
    # ─────────────────────────────────────────────────────────────────────────

    @run_in_thread
    def extract_text(self):
        """Extract text from all loaded PDFs (or selected page range)."""
        pdfs = [f for f in self.loaded_files if f.lower().endswith(".pdf")]
        if not pdfs:
            self.root.after(0, lambda: messagebox.showwarning("No PDFs", "Please load at least one PDF file."))
            return

        page_range = self.page_range_var.get().strip() or None

        self._clear_output()
        self._set_progress(0)
        self._set_status("⏳  Extracting text…")

        total = len(pdfs)
        for i, file_path in enumerate(pdfs, start=1):
            try:
                name = os.path.basename(file_path)
                self._write_output(f"\n{'━' * 56}", "heading")
                self._write_output(f"  FILE: {name}", "heading")
                self._write_output(f"{'━' * 56}", "heading")

                text = pdf_utils.extract_text_from_pdf(file_path, page_range)
                self._write_output(text)

                prog = int((i / total) * 100)
                self._set_progress(prog)
                self._set_status(f"⏳  Processed {i}/{total}: {name}")

            except Exception as ex:
                self._write_output(f"\n⚠  Error in {os.path.basename(file_path)}: {ex}", "error")

        self._set_status("✅  Text extraction complete")
        self._set_progress(100)

    # ─────────────────────────────────────────────────────────────────────────
    #  PDF MERGING
    # ─────────────────────────────────────────────────────────────────────────

    @run_in_thread
    def merge_pdfs(self):
        """Merge all loaded PDFs into one output file."""
        pdfs = [f for f in self.loaded_files if f.lower().endswith(".pdf")]
        if len(pdfs) < 2:
            self.root.after(0, lambda: messagebox.showwarning("Not Enough PDFs", "Please load at least 2 PDF files to merge."))
            return

        # Determine output path
        output_name = self.merge_output_var.get().strip() or "merged_output.pdf"
        if not output_name.lower().endswith(".pdf"):
            output_name += ".pdf"

        # Ask user where to save
        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=output_name,
            filetypes=[("PDF Files", "*.pdf")],
            title="Save Merged PDF As…",
        )
        if not save_path:
            self._set_status("ℹ  Merge cancelled")
            return

        page_range_str = self.page_range_var.get().strip()

        # Build per-file page ranges if a global range was specified
        page_ranges = None
        if page_range_str:
            page_ranges = {fp: page_range_str for fp in pdfs}

        self._clear_output()
        self._set_progress(0)
        self._set_status("⏳  Merging PDFs…")

        try:
            result = pdf_utils.merge_pdfs(pdfs, save_path, page_ranges)
            self._write_output(result, "success")
            self._write_output(f"\nFiles merged:\n" +
                               "\n".join(f"  • {os.path.basename(fp)}" for fp in pdfs))
            if page_range_str:
                self._write_output(f"\nPage range applied: {page_range_str}", "warning")
            self._set_status(f"✅  Merged → {os.path.basename(save_path)}")
            self._set_progress(100)
        except Exception as ex:
            self._write_output(f"❌  Merge failed: {ex}", "error")
            self._set_status(f"❌  Merge error: {ex}")
            self._set_progress(0)

    # ─────────────────────────────────────────────────────────────────────────
    #  KEYWORD SEARCH
    # ─────────────────────────────────────────────────────────────────────────

    @run_in_thread
    def search_keyword(self):
        """Search for keyword across all loaded PDFs and highlight results."""
        pdfs = [f for f in self.loaded_files if f.lower().endswith(".pdf")]
        if not pdfs:
            self.root.after(0, lambda: messagebox.showwarning("No PDFs", "Please load at least one PDF file to search."))
            return

        keyword = self.keyword_var.get().strip()
        if not keyword:
            self.root.after(0, lambda: messagebox.showwarning(
                "No Keyword", "Please enter a keyword to search for."))
            return

        case_sensitive = self.case_sensitive_var.get()

        self._clear_output()
        self._set_progress(0)
        self._set_status(f"🔍  Searching for: '{keyword}'…")

        try:
            results = pdf_utils.search_keyword_in_pdfs(
                pdfs, keyword, case_sensitive)

            total_matches = sum(len(v) for v in results.values())
            self._write_output(
                f"Search results for  '{keyword}'  "
                f"({'case-sensitive' if case_sensitive else 'case-insensitive'})",
                "heading")
            self._write_output("─" * 56, "heading")

            if total_matches == 0:
                self._write_output("\n  No matches found.", "warning")
            else:
                for file_path, pages in results.items():
                    name = os.path.basename(file_path)
                    if pages:
                        page_list = ", ".join(str(p) for p in pages)
                        self._write_output(f"\n  {name}")
                        self._write_output(
                            f"    Found on pages: {page_list}", "keyword")
                    else:
                        self._write_output(f"\n  {name}  →  not found", "warning")

                self._write_output(
                    f"\n  Total: {total_matches} page(s) matched across "
                    f"{sum(1 for v in results.values() if v)} file(s).",
                    "success")

            self._set_status(
                f"✅  Search complete  •  {total_matches} match(es) for '{keyword}'")
            self._set_progress(100)

        except Exception as ex:
            self._write_output(f"❌  Search error: {ex}", "error")
            self._set_status(f"❌  Search failed: {ex}")

    # ─────────────────────────────────────────────────────────────────────────
    #  OCR
    # ─────────────────────────────────────────────────────────────────────────

    @run_in_thread
    def apply_ocr(self):
        """Run OCR on loaded PDFs (for scanned/image-based PDFs)."""
        pdfs = [f for f in self.loaded_files if f.lower().endswith(".pdf")]
        if not pdfs:
            self.root.after(0, lambda: messagebox.showwarning("No PDFs", "Please load at least one PDF file."))
            return

        available, msg = ocr_utils.is_ocr_available()
        if not available:
            self.root.after(0, lambda: messagebox.showerror("OCR Unavailable", msg))
            return

        page_range = self.page_range_var.get().strip() or None
        lang       = self.ocr_lang_var.get().strip()   or "eng"

        self._clear_output()
        self._set_progress(0)
        self._set_status("🔬  Running OCR…")

        total = len(pdfs)
        for file_idx, file_path in enumerate(pdfs, start=1):
            try:
                name = os.path.basename(file_path)
                self._write_output(f"\n{'━' * 56}", "heading")
                self._write_output(f"  OCR: {name}", "heading")
                self._write_output(f"{'━' * 56}", "heading")

                def _progress(cur, tot, fi=file_idx, fn=file_path):
                    overall = int(((fi - 1 + cur / tot) / total) * 100)
                    self._set_progress(overall)
                    self._set_status(
                        f"🔬  OCR page {cur}/{tot}  •  {os.path.basename(fn)}")

                # Try common Poppler paths on Windows
                poppler_paths = [
                    r"C:\poppler\Library\bin",
                    r"C:\Program Files\poppler\bin", 
                    r"C:\Program Files (x86)\poppler\bin"
                ]
                
                poppler_path = None
                for path in poppler_paths:
                    if os.path.isdir(path):
                        poppler_path = path
                        break
                
                text = ocr_utils.perform_ocr(
                    file_path,
                    page_range=page_range,
                    lang=lang,
                    progress_callback=_progress,
                    poppler_path=poppler_path,
                )
                self._write_output(text)

            except Exception as ex:
                self._write_output(f"❌  OCR error ({os.path.basename(file_path)}): {ex}", "error")

        self._set_status("✅  OCR complete")
        self._set_progress(100)

    # ─────────────────────────────────────────────────────────────────────────
    #  WORD UTILITIES
    # ─────────────────────────────────────────────────────────────────────────

    @run_in_thread
    def run_pdf_to_word(self):
        pdfs = [f for f in self.loaded_files if f.lower().endswith(".pdf")]
        if not pdfs:
            self.root.after(0, lambda: messagebox.showwarning("No PDF Files", "Please load at least one PDF file to convert."))
            return

        ok, msg = word_utils.check_pdf_to_word_deps()
        if not ok:
            self.root.after(0, lambda: messagebox.showerror("Dependency Error", msg))
            return

        page_range = self.page_range_var.get().strip() or None

        save_path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            initialfile=os.path.splitext(os.path.basename(pdfs[0]))[0] + ".docx",
            filetypes=[("Word Files", "*.docx")],
            title="Save Extracted Word File As…",
        )
        if not save_path:
            return

        self._clear_output()
        self._set_progress(0)
        self._set_status("⏳  Converting PDF to Word…")

        try:
            self._write_output(f"Converting: {os.path.basename(pdfs[0])} -> Word...", "heading")
            res = word_utils.pdf_to_word(pdfs[0], save_path, page_range=page_range)
            self._write_output(res, "success")
            self._set_status(f"✅  Saved → {os.path.basename(save_path)}")
            self._set_progress(100)
        except Exception as ex:
            self._write_output(f"❌  Conversion failed: {ex}", "error")
            self._set_status("❌  Conversion error")
            self._set_progress(0)

    @run_in_thread
    def run_word_to_pdf(self):
        words = [f for f in self.loaded_files if f.lower().endswith(".docx")]
        if not words:
            self.root.after(0, lambda: messagebox.showwarning("No Word Files", "Please load at least one Word file to convert."))
            return

        ok, msg = word_utils.check_word_to_pdf_deps()
        if not ok:
            self.root.after(0, lambda: messagebox.showerror("Dependency Error", msg))
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            initialfile=os.path.splitext(os.path.basename(words[0]))[0] + ".pdf",
            filetypes=[("PDF Files", "*.pdf")],
            title="Save PDF File As…",
        )
        if not save_path:
            return

        self._clear_output()
        self._set_progress(0)
        self._set_status("⏳  Converting Word to PDF…")

        try:
            self._write_output(f"Converting: {os.path.basename(words[0])} -> PDF...", "heading")
            res = word_utils.word_to_pdf(words[0], save_path)
            self._write_output(res, "success")
            self._set_status(f"✅  Saved → {os.path.basename(save_path)}")
            self._set_progress(100)
        except Exception as ex:
            self._write_output(f"❌  Conversion failed: {ex}", "error")
            self._set_status("❌  Conversion error")
            self._set_progress(0)

    @run_in_thread
    def run_merge_word(self):
        words = [f for f in self.loaded_files if f.lower().endswith(".docx")]
        if len(words) < 2:
            self.root.after(0, lambda: messagebox.showwarning("Not Enough Word Files", "Please load at least two Word files to merge."))
            return

        ok, msg = word_utils.check_word_merge_deps()
        if not ok:
            self.root.after(0, lambda: messagebox.showerror("Dependency Error", msg))
            return

        save_path = filedialog.asksaveasfilename(
            defaultextension=".docx",
            initialfile="merged_output.docx",
            filetypes=[("Word Files", "*.docx")],
            title="Save Merged Word File As…",
        )
        if not save_path:
            return

        self._clear_output()
        self._set_progress(0)
        self._set_status("⏳  Merging Word Files…")

        try:
            self._write_output("Merging Word files:", "heading")
            for w in words:
                self._write_output(f"  • {os.path.basename(w)}")
            res = word_utils.merge_word_files(words, save_path)
            self._write_output(f"\n{res}", "success")
            self._set_status(f"✅  Merged → {os.path.basename(save_path)}")
            self._set_progress(100)
        except Exception as ex:
            self._write_output(f"❌  Merge failed: {ex}", "error")
            self._set_status("❌  Merge error")
            self._set_progress(0)

    # ─────────────────────────────────────────────────────────────────────────
    #  SAVE TEXT
    # ─────────────────────────────────────────────────────────────────────────

    def save_text(self):
        """Save the current output text to a .txt file."""
        content = self.output_text.get("1.0", END).strip()
        if not content:
            messagebox.showwarning("Empty Output", "There is no text to save.")
            return

        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile="extracted_text.txt",
            filetypes=[("Text Files", "*.txt"), ("All Files", "*.*")],
            title="Save Extracted Text As…",
        )
        if not path:
            return

        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._set_status(f"💾  Saved → {os.path.basename(path)}")
            messagebox.showinfo("Saved", f"Text saved to:\n{path}")
        except Exception as ex:
            messagebox.showerror("Save Error", str(ex))

    # ─────────────────────────────────────────────────────────────────────────
    #  GUARD
    # ─────────────────────────────────────────────────────────────────────────

    def _check_files(self, min_count: int = 1, action: str = "") -> bool:
        """Return True if enough files are loaded; show a warning otherwise."""
        if len(self.loaded_files) < min_count:
            verb = f"to {action}" if action else ""
            msg  = (f"Please load at least {min_count} file(s) {verb}."
                    if min_count > 1
                    else "Please load at least one file.")
            self.root.after(0, lambda: messagebox.showwarning("No Files", msg))
            return False
        return True

    # ─────────────────────────────────────────────────────────────────────────
    #  ABOUT
    # ─────────────────────────────────────────────────────────────────────────

    def _show_about(self):
        messagebox.showinfo(
            "About",
            "Advanced PDF Text Extractor & Merger\n"
            "Version 1.0\n\n"
            "Tech Stack:\n"
            "  • Python + Tkinter (GUI)\n"
            "  • pdfminer.six (text extraction)\n"
            "  • PyPDF2 (merging & metadata)\n"
            "  • Tesseract OCR (scanned PDFs)\n\n"
            "Double-click a file in the list to view its metadata."
        )
