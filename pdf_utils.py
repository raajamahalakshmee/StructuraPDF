"""
pdf_utils.py
------------
Core PDF processing utilities:
  - Text extraction using pdfminer.six
  - PDF merging with optional page ranges
  - Keyword search across uploaded PDFs
  - Metadata retrieval using PyPDF2
"""

import os
import re
from io import StringIO
from typing import Optional

# ── PyPDF2 (merging, metadata) ────────────────────────────────────────────────
try:
    from PyPDF2 import PdfReader, PdfWriter
except ImportError:
    raise ImportError("PyPDF2 is not installed. Run: pip install PyPDF2")

# ── pdfminer.six (text extraction) ────────────────────────────────────────────
try:
    from pdfminer.high_level import extract_text_to_fp
    from pdfminer.layout import LAParams
    from pdfminer.pdfpage import PDFPage
    from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
    from pdfminer.converter import TextConverter
except ImportError:
    raise ImportError("pdfminer.six is not installed. Run: pip install pdfminer.six")


# ─────────────────────────────────────────────────────────────────────────────
#  TEXT EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_text_from_pdf(file_path: str, page_range: Optional[str] = None) -> str:
    """
    Extract text from a PDF file using pdfminer.six.

    Args:
        file_path   : Absolute path to the PDF file.
        page_range  : Optional string like "1-3, 5, 7-9" (1-indexed).
                      If None, all pages are extracted.

    Returns:
        Extracted text as a single string.

    Raises:
        FileNotFoundError : If the file doesn't exist.
        ValueError        : If the page range is invalid.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    pages_to_extract = _parse_page_range(page_range) if page_range else None

    resource_manager = PDFResourceManager()
    output_buffer = StringIO()
    laparams = LAParams()

    converter = TextConverter(resource_manager, output_buffer, laparams=laparams)
    interpreter = PDFPageInterpreter(resource_manager, converter)

    extracted_parts = []

    with open(file_path, "rb") as pdf_file:
        for page_num, page in enumerate(PDFPage.get_pages(pdf_file, check_extractable=True), start=1):
            if pages_to_extract is None or page_num in pages_to_extract:
                interpreter.process_page(page)
                text = output_buffer.getvalue()
                extracted_parts.append(f"--- Page {page_num} ---\n{text}")
                # Reset buffer after each page
                output_buffer.truncate(0)
                output_buffer.seek(0)

    converter.close()
    output_buffer.close()

    full_text = "\n".join(extracted_parts)
    if not full_text.strip():
        return "[No selectable text found. Try using OCR for scanned PDFs.]"
    return full_text


# ─────────────────────────────────────────────────────────────────────────────
#  PDF MERGING
# ─────────────────────────────────────────────────────────────────────────────

def merge_pdfs(file_paths: list[str], output_path: str,
               page_ranges: Optional[dict[str, str]] = None) -> str:
    """
    Merge multiple PDF files into one output PDF.

    Args:
        file_paths   : List of absolute paths to input PDFs.
        output_path  : Destination path for the merged PDF.
        page_ranges  : Optional dict mapping file_path → page_range string.
                       e.g. {"a.pdf": "1-3", "b.pdf": "2, 4-6"}
                       If a file has no entry, all its pages are included.

    Returns:
        Success message string.

    Raises:
        FileNotFoundError : If any input file doesn't exist.
        ValueError        : If no valid pages are found to merge.
    """
    if not file_paths:
        raise ValueError("No PDF files provided for merging.")

    writer = PdfWriter()

    for file_path in file_paths:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File not found: {file_path}")

        reader = PdfReader(file_path)
        total_pages = len(reader.pages)

        # Determine which pages to include
        range_str = (page_ranges or {}).get(file_path)
        if range_str:
            page_nums = _parse_page_range(range_str, max_pages=total_pages)
        else:
            page_nums = list(range(1, total_pages + 1))

        for page_num in page_nums:
            idx = page_num - 1  # 0-indexed
            if 0 <= idx < total_pages:
                writer.add_page(reader.pages[idx])

    if len(writer.pages) == 0:
        raise ValueError("No pages were added to the merged document.")

    with open(output_path, "wb") as out_file:
        writer.write(out_file)

    return f"✅ Merged PDF saved to: {output_path} ({len(writer.pages)} pages)"


# ─────────────────────────────────────────────────────────────────────────────
#  KEYWORD SEARCH
# ─────────────────────────────────────────────────────────────────────────────

def search_keyword_in_pdfs(file_paths: list[str], keyword: str,
                           case_sensitive: bool = False) -> dict[str, list[int]]:
    """
    Search for a keyword across one or more PDF files.

    Args:
        file_paths      : List of PDF file paths to search.
        keyword         : The keyword / phrase to look for.
        case_sensitive  : Whether the search is case-sensitive (default: False).

    Returns:
        Dictionary mapping file_path → list of page numbers where keyword appears.

    Raises:
        ValueError : If keyword is empty.
    """
    if not keyword.strip():
        raise ValueError("Search keyword cannot be empty.")

    results: dict[str, list[int]] = {}

    flags = 0 if case_sensitive else re.IGNORECASE
    pattern = re.compile(re.escape(keyword), flags)

    for file_path in file_paths:
        if not os.path.isfile(file_path):
            continue

        matching_pages: list[int] = []

        resource_manager = PDFResourceManager()
        laparams = LAParams()

        with open(file_path, "rb") as pdf_file:
            for page_num, page in enumerate(
                    PDFPage.get_pages(pdf_file, check_extractable=True), start=1):
                output_buffer = StringIO()
                converter = TextConverter(resource_manager, output_buffer, laparams=laparams)
                interpreter = PDFPageInterpreter(resource_manager, converter)
                interpreter.process_page(page)

                text = output_buffer.getvalue()
                converter.close()
                output_buffer.close()

                if pattern.search(text):
                    matching_pages.append(page_num)

        results[file_path] = matching_pages

    return results


# ─────────────────────────────────────────────────────────────────────────────
#  METADATA
# ─────────────────────────────────────────────────────────────────────────────

def get_pdf_metadata(file_path: str) -> dict:
    """
    Retrieve metadata for a PDF file.

    Args:
        file_path : Absolute path to the PDF file.

    Returns:
        Dictionary containing:
          - file_name   : Base name of the file
          - file_size   : File size formatted as KB/MB
          - page_count  : Number of pages
          - title       : PDF title (from metadata), or "N/A"
          - author      : PDF author, or "N/A"
          - subject     : PDF subject, or "N/A"
          - creator     : PDF creator application, or "N/A"
          - encrypted   : Whether the PDF is encrypted

    Raises:
        FileNotFoundError : If the file doesn't exist.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    reader = PdfReader(file_path)
    meta = reader.metadata or {}

    size_bytes = os.path.getsize(file_path)
    if size_bytes >= 1_048_576:
        size_str = f"{size_bytes / 1_048_576:.2f} MB"
    else:
        size_str = f"{size_bytes / 1_024:.2f} KB"

    return {
        "file_name"  : os.path.basename(file_path),
        "file_size"  : size_str,
        "page_count" : len(reader.pages),
        "title"      : meta.get("/Title", "N/A") or "N/A",
        "author"     : meta.get("/Author", "N/A") or "N/A",
        "subject"    : meta.get("/Subject", "N/A") or "N/A",
        "creator"    : meta.get("/Creator", "N/A") or "N/A",
        "encrypted"  : reader.is_encrypted,
    }


# ─────────────────────────────────────────────────────────────────────────────
#  HELPER: PAGE RANGE PARSER
# ─────────────────────────────────────────────────────────────────────────────

def _parse_page_range(range_str: str, max_pages: Optional[int] = None) -> list[int]:
    """
    Parse a human-readable page range string into a sorted list of page numbers.

    Supports formats like: "1-3, 5, 7-9", "2", "1, 3-5, 8"

    Args:
        range_str  : Human-readable range string (1-indexed).
        max_pages  : Optional upper bound; out-of-range numbers are ignored.

    Returns:
        Sorted list of unique integer page numbers.

    Raises:
        ValueError : If the format is invalid or a range is reversed.
    """
    pages: set[int] = set()

    # Strip whitespace and split by comma
    parts = [p.strip() for p in range_str.split(",") if p.strip()]

    for part in parts:
        if "-" in part:
            bounds = part.split("-")
            if len(bounds) != 2:
                raise ValueError(f"Invalid page range segment: '{part}'")
            try:
                start, end = int(bounds[0].strip()), int(bounds[1].strip())
            except ValueError:
                raise ValueError(f"Non-integer values in range: '{part}'")
            if start > end:
                raise ValueError(f"Start page {start} is greater than end page {end}.")
            for p in range(start, end + 1):
                if max_pages is None or p <= max_pages:
                    pages.add(p)
        else:
            try:
                p = int(part)
            except ValueError:
                raise ValueError(f"Invalid page number: '{part}'")
            if max_pages is None or p <= max_pages:
                pages.add(p)

    if not pages:
        raise ValueError(f"No valid pages found in range: '{range_str}'")

    return sorted(pages)
