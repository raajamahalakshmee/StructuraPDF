"""
ocr_utils.py
------------
OCR (Optical Character Recognition) utilities for scanned / image-based PDFs.

Dependencies:
  - Tesseract OCR binary   : https://github.com/UB-Mannheim/tesseract/wiki
  - pytesseract            : pip install pytesseract
  - pdf2image              : pip install pdf2image
  - Pillow                 : pip install Pillow
  - poppler (for pdf2image): https://github.com/oschwartz10612/poppler-windows/releases

How Tesseract works here:
  1. Each PDF page is rendered as a high-resolution image using pdf2image.
  2. pytesseract sends each image to Tesseract and retrieves the recognized text.
  3. Results are concatenated per page and returned.
"""

import os
import sys
from typing import Optional, Callable

# ── pytesseract ───────────────────────────────────────────────────────────────
try:
    import pytesseract
except ImportError:
    pytesseract = None  # Graceful degradation; checked at runtime

# ── pdf2image ─────────────────────────────────────────────────────────────────
try:
    from pdf2image import convert_from_path
except ImportError:
    convert_from_path = None  # Graceful degradation

# ── Pillow ────────────────────────────────────────────────────────────────────
try:
    from PIL import Image
except ImportError:
    Image = None


# ─────────────────────────────────────────────────────────────────────────────
#  TESSERACT PATH CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

# Default Tesseract install location on Windows.
# Update this path if Tesseract is installed elsewhere on your system.
DEFAULT_TESSERACT_CMD = r"C:\Program Files\Tesseract-OCR\tesseract.exe"


def configure_tesseract(custom_path: Optional[str] = None) -> bool:
    """
    Configure pytesseract to point at the Tesseract binary.

    Args:
        custom_path : Optional custom path to tesseract.exe.
                      Falls back to DEFAULT_TESSERACT_CMD if not provided.

    Returns:
        True  if Tesseract was found and configured.
        False if Tesseract binary was not found.
    """
    if pytesseract is None:
        return False

    tesseract_path = custom_path or DEFAULT_TESSERACT_CMD

    if os.path.isfile(tesseract_path):
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        return True

    # Try to find tesseract in PATH
    import shutil
    if shutil.which("tesseract"):
        # It's on PATH; pytesseract will find it automatically
        return True

    return False


def is_ocr_available() -> tuple[bool, str]:
    """
    Check whether all OCR dependencies are present.

    Returns:
        (available: bool, message: str)
    """
    missing = []

    if pytesseract is None:
        missing.append("pytesseract (pip install pytesseract)")
    if convert_from_path is None:
        missing.append("pdf2image (pip install pdf2image)")
    if Image is None:
        missing.append("Pillow (pip install Pillow)")

    if missing:
        return False, "Missing OCR dependencies:\n  * " + "\n  * ".join(missing)

    if not configure_tesseract():
        return False, (
            "Tesseract OCR binary not found.\n"
            "Install from: https://github.com/UB-Mannheim/tesseract/wiki\n"
            f"Expected path: {DEFAULT_TESSERACT_CMD}"
        )

    # Check for Poppler
    import shutil
    poppler_in_path = shutil.which("pdftoppm") or shutil.which("pdfinfo")
    if not poppler_in_path:
        # Check common installation paths
        common_paths = [
            r"C:\poppler\Library\bin",
            r"C:\Program Files\poppler\bin",
            r"C:\Program Files (x86)\poppler\bin"
        ]
        poppler_found = any(os.path.isdir(path) for path in common_paths)
        
        if not poppler_found:
            return False, (
                "Poppler not found. Poppler is required for OCR.\n\n"
                "To install Poppler on Windows:\n"
                "1. Download from: https://github.com/oschwartz10612/poppler-windows/releases\n"
                "2. Extract to: C:\\poppler\\\n"
                "3. The app will automatically find it at C:\\poppler\\Library\\bin\n\n"
                "Or add Poppler's bin folder to your system PATH."
            )

    return True, "OCR is ready."


# ─────────────────────────────────────────────────────────────────────────────
#  CORE OCR FUNCTION
# ─────────────────────────────────────────────────────────────────────────────

def perform_ocr(file_path: str,
                page_range: Optional[str] = None,
                dpi: int = 300,
                lang: str = "eng",
                progress_callback: Optional[Callable[[int, int], None]] = None,
                poppler_path: Optional[str] = None) -> str:
    """
    Perform OCR on a scanned / image-based PDF.

    Args:
        file_path         : Absolute path to the PDF file.
        page_range        : Optional page range string like "1-3, 5" (1-indexed).
                            If None, all pages are OCR'd.
        dpi               : Resolution for rendering PDF pages (higher = better quality).
                            300 is recommended; 150 is faster but less accurate.
        lang              : Tesseract language code (e.g. "eng", "fra", "deu").
                            Must match installed Tesseract language packs.
        progress_callback : Optional callable(current_page, total_pages) for UI updates.
        poppler_path      : Optional path to Poppler's bin directory (Windows).
                            e.g. r"C:\poppler\Library\bin"

    Returns:
        OCR-extracted text as a string, with page separators.

    Raises:
        RuntimeError      : If OCR dependencies are not available.
        FileNotFoundError : If the input file doesn't exist.
        ValueError        : If the page range is invalid.
    """
    # ── Dependency check ──────────────────────────────────────────────────────
    available, msg = is_ocr_available()
    if not available:
        raise RuntimeError(msg)

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    # ── Render PDF pages to images ────────────────────────────────────────────
    convert_kwargs = {"dpi": dpi}
    if poppler_path and os.path.isdir(poppler_path):
        convert_kwargs["poppler_path"] = poppler_path

    images = convert_from_path(file_path, **convert_kwargs)
    total_pages = len(images)

    # ── Determine which pages to OCR ─────────────────────────────────────────
    if page_range:
        from pdf_utils import _parse_page_range
        pages_to_ocr = _parse_page_range(page_range, max_pages=total_pages)
    else:
        pages_to_ocr = list(range(1, total_pages + 1))

    # ── Run OCR per page ──────────────────────────────────────────────────────
    ocr_results: list[str] = []

    for i, page_num in enumerate(pages_to_ocr, start=1):
        img_index = page_num - 1  # 0-indexed list
        if img_index < 0 or img_index >= total_pages:
            continue

        image = images[img_index]

        # Pre-process: convert to grayscale for better OCR accuracy
        grayscale_image = image.convert("L")

        # Run Tesseract
        text = pytesseract.image_to_string(grayscale_image, lang=lang)
        ocr_results.append(f"--- Page {page_num} (OCR) ---\n{text}")

        # Notify UI of progress
        if progress_callback:
            progress_callback(i, len(pages_to_ocr))

    full_text = "\n\n".join(ocr_results)
    if not full_text.strip():
        return "[OCR produced no text. Ensure the PDF contains readable images.]"

    return full_text


# ─────────────────────────────────────────────────────────────────────────────
#  UTILITY: LIST AVAILABLE TESSERACT LANGUAGES
# ─────────────────────────────────────────────────────────────────────────────

def get_available_languages() -> list[str]:
    """
    Return a list of installed Tesseract language codes.

    Returns:
        List of language code strings (e.g. ["eng", "fra"]).
        Returns ["eng"] as fallback if listing fails.
    """
    if pytesseract is None or not configure_tesseract():
        return ["eng"]

    try:
        langs = pytesseract.get_languages(config="")
        return [lang for lang in langs if lang != "osd"]
    except Exception:
        return ["eng"]
