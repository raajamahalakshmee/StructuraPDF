"""
main.py
-------
Entry point for the Advanced PDF Text Extractor and Merger System.

Usage:
    python main.py

Ensure all dependencies are installed:
    pip install -r requirements.txt

External binary requirements (see README.md for setup):
    - Tesseract OCR  : https://github.com/UB-Mannheim/tesseract/wiki
    - Poppler        : https://github.com/oschwartz10612/poppler-windows/releases
"""

import sys
import tkinter as tk
from tkinter import messagebox


def check_python_version():
    """Enforce Python 3.9+ (required for type-hint syntax used in the project)."""
    if sys.version_info < (3, 9):
        print("ERROR: Python 3.9 or higher is required.")
        sys.exit(1)


def check_core_dependencies():
    """Verify that required packages are importable and show a helpful error if not."""
    missing = []

    for pkg, pip_name in [
        ("PyPDF2",    "PyPDF2"),
        ("pdfminer",  "pdfminer.six"),
    ]:
        try:
            __import__(pkg)
        except ImportError:
            missing.append(pip_name)

    if missing:
        msg = (
            "Missing required packages:\n\n"
            + "\n".join(f"  • {p}" for p in missing)
            + "\n\nInstall them with:\n"
            "  pip install -r requirements.txt"
        )
        # Try to show a GUI dialog if Tkinter is available; fall back to print
        try:
            root = tk.Tk()
            root.withdraw()
            messagebox.showerror("Dependency Error", msg)
            root.destroy()
        except Exception:
            print(msg)
        sys.exit(1)


def main():
    """Bootstrap the Tkinter event loop and launch the application."""
    # ── Pre-flight checks ─────────────────────────────────────────────────────
    check_python_version()
    check_core_dependencies()

    # ── Import after dependency check ─────────────────────────────────────────
    from gui import PDFConverterApp

    # ── Create and configure root window ─────────────────────────────────────
    root = tk.Tk()

    # Enable high-DPI awareness on Windows
    try:
        from ctypes import windll
        windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass  # Not on Windows, or DPI API unavailable

    # ── Launch application ────────────────────────────────────────────────────
    app = PDFConverterApp(root)

    # Graceful exit on window close
    root.protocol("WM_DELETE_WINDOW", root.quit)

    root.mainloop()


if __name__ == "__main__":
    main()
