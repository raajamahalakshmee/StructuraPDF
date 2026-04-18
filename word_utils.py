"""
word_utils.py
-------------
Word document processing utilities:
  - Word (.docx) → PDF conversion
  - PDF → Word (.docx) conversion
  - Merge multiple Word (.docx) files into one

Dependencies:
  - python-docx  : pip install python-docx   (merge & read Word)
  - docx2pdf     : pip install docx2pdf       (Word → PDF, needs MS Word on Windows)
  - pdf2docx     : pip install pdf2docx       (PDF → Word)
"""

import os
from typing import Optional

# ── python-docx ───────────────────────────────────────────────────────────────
try:
    from docx import Document
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement
    import copy
except ImportError:
    Document = None

# ── docx2pdf ──────────────────────────────────────────────────────────────────
try:
    from docx2pdf import convert as docx2pdf_convert
except ImportError:
    docx2pdf_convert = None

# ── pdf2docx ──────────────────────────────────────────────────────────────────
try:
    from pdf2docx import Converter
except ImportError:
    Converter = None


# ─────────────────────────────────────────────────────────────────────────────
#  DEPENDENCY CHECKS
# ─────────────────────────────────────────────────────────────────────────────

def check_word_to_pdf_deps() -> tuple[bool, str]:
    """Check deps for Word → PDF."""
    if Document is None:
        return False, "python-docx not installed.\n  pip install python-docx"
    if docx2pdf_convert is None:
        return False, (
            "docx2pdf not installed.\n  pip install docx2pdf\n\n"
            "NOTE (Windows): docx2pdf requires Microsoft Word to be installed."
        )
    return True, "OK"


def check_pdf_to_word_deps() -> tuple[bool, str]:
    """Check deps for PDF → Word."""
    if Converter is None:
        return False, "pdf2docx not installed.\n  pip install pdf2docx"
    return True, "OK"


def check_word_merge_deps() -> tuple[bool, str]:
    """Check deps for merging Word files."""
    if Document is None:
        return False, "python-docx not installed.\n  pip install python-docx"
    return True, "OK"


# ─────────────────────────────────────────────────────────────────────────────
#  WORD → PDF
# ─────────────────────────────────────────────────────────────────────────────

def word_to_pdf(docx_path: str, output_path: str) -> str:
    """
    Convert a .docx file to PDF.

    On Windows this uses Microsoft Word via COM automation (Word must be installed).
    On macOS/Linux it uses LibreOffice (must be installed separately).

    Args:
        docx_path   : Absolute path to the input .docx file.
        output_path : Destination path for the output .pdf file.

    Returns:
        Success message string.

    Raises:
        RuntimeError      : If docx2pdf is not installed.
        FileNotFoundError : If the input file doesn't exist.
    """
    ok, msg = check_word_to_pdf_deps()
    if not ok:
        raise RuntimeError(msg)

    if not os.path.isfile(docx_path):
        raise FileNotFoundError(f"File not found: {docx_path}")

    # Ensure output directory exists
    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    docx2pdf_convert(docx_path, output_path)

    if not os.path.isfile(output_path):
        raise RuntimeError("Conversion completed but output file was not created.")

    size = os.path.getsize(output_path) / 1024
    return f"✅ Word → PDF: {os.path.basename(output_path)}  ({size:.1f} KB)"


# ─────────────────────────────────────────────────────────────────────────────
#  PDF → WORD
# ─────────────────────────────────────────────────────────────────────────────

def pdf_to_word(pdf_path: str, output_path: str,
                page_range: Optional[str] = None,
                progress_callback=None) -> str:
    """
    Convert a PDF file to a .docx Word document.

    Args:
        pdf_path          : Absolute path to the input PDF file.
        output_path       : Destination path for the output .docx file.
        page_range        : Optional page range like "1-3, 5" (1-indexed).
                            If None, all pages are converted.
        progress_callback : Optional callable(current, total) for UI updates.

    Returns:
        Success message string.

    Raises:
        RuntimeError      : If pdf2docx is not installed.
        FileNotFoundError : If the input file doesn't exist.
    """
    ok, msg = check_pdf_to_word_deps()
    if not ok:
        raise RuntimeError(msg)

    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"File not found: {pdf_path}")

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Parse page range to start/end (pdf2docx uses start/end, 0-indexed)
    start_page, end_page = 0, None  # defaults = all pages

    if page_range:
        from pdf_utils import _parse_page_range
        pages = _parse_page_range(page_range)
        if pages:
            start_page = pages[0] - 1   # convert to 0-indexed
            end_page   = pages[-1]       # pdf2docx end is exclusive upper bound

    cv = Converter(pdf_path)
    cv.convert(output_path, start=start_page, end=end_page)
    cv.close()

    if not os.path.isfile(output_path):
        raise RuntimeError("Conversion completed but output file was not created.")

    size = os.path.getsize(output_path) / 1024
    return f"✅ PDF → Word: {os.path.basename(output_path)}  ({size:.1f} KB)"


# ─────────────────────────────────────────────────────────────────────────────
#  MERGE WORD FILES
# ─────────────────────────────────────────────────────────────────────────────

def merge_word_files(file_paths: list[str], output_path: str,
                     add_page_break: bool = True) -> str:
    """
    Merge two or more .docx files into a single Word document.

    Each source document's content is appended after the previous one.
    An optional page break is inserted between documents.

    Args:
        file_paths     : List of absolute paths to input .docx files.
        output_path    : Destination path for the merged .docx.
        add_page_break : If True, inserts a page break between documents.

    Returns:
        Success message string.

    Raises:
        RuntimeError      : If python-docx is not installed.
        FileNotFoundError : If any input file doesn't exist.
        ValueError        : If fewer than 2 files are provided.
    """
    ok, msg = check_word_merge_deps()
    if not ok:
        raise RuntimeError(msg)

    if len(file_paths) < 2:
        raise ValueError("Please provide at least 2 Word files to merge.")

    for fp in file_paths:
        if not os.path.isfile(fp):
            raise FileNotFoundError(f"File not found: {fp}")

    out_dir = os.path.dirname(output_path)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)

    # Open the first document as the base
    merged_doc = Document(file_paths[0])

    for i, file_path in enumerate(file_paths[1:], start=1):
        if add_page_break:
            # Insert a page break at the end of the current content
            _add_page_break(merged_doc)

        # Open the next document and copy its elements with images
        sub_doc = Document(file_path)
        _append_document_with_images(merged_doc, sub_doc)

    merged_doc.save(output_path)

    page_count = _count_paragraphs(merged_doc)
    return (
        f"✅ Merged {len(file_paths)} Word files → {os.path.basename(output_path)}\n"
        f"   ({page_count} paragraphs total)"
    )


# ─────────────────────────────────────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _add_page_break(doc: "Document"):
    """Insert a page-break paragraph at the end of a Document."""
    paragraph = doc.add_paragraph()
    run = paragraph.add_run()
    br = OxmlElement("w:br")
    br.set(qn("w:type"), "page")
    run._r.append(br)


def _count_paragraphs(doc: "Document") -> int:
    """Return total number of paragraphs in a Document."""
    return len(doc.paragraphs)


def _append_document_with_images(merged_doc: "Document", sub_doc: "Document"):
    """
    Copy all content from sub_doc into merged_doc, including images.

    Images in Word are stored as separate parts with relationships linking them
    to the document. This function copies image parts and updates relationship IDs
    so images appear correctly in the merged document.
    """
    # Build a map of image relationships from sub_doc
    # Key: old rId in sub_doc, Value: new_rId in merged_doc
    image_rel_map = {}

    # Find all image relationships in the sub document
    for rel_id, rel in sub_doc.part.rels.items():
        if "image" in rel.target_ref:
            # Get the image part
            image_part = rel.target_part
            # Add this image part to the merged document and get new relationship ID
            # Note: relate_to() returns the rId string directly
            new_rId = merged_doc.part.relate_to(image_part, rel.reltype)
            # Map old rId to new rId
            image_rel_map[rel_id] = new_rId

    # Copy all body elements, updating image references
    for element in sub_doc.element.body:
        # Deep copy the element
        new_element = copy.deepcopy(element)

        # Update image relationship IDs in the copied element
        # Images are referenced via blip elements with r:embed attributes
        for blip in new_element.iter("{http://schemas.openxmlformats.org/drawingml/2006/main}blip"):
            embed_attr = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed"
            old_rId = blip.get(embed_attr)
            if old_rId and old_rId in image_rel_map:
                blip.set(embed_attr, image_rel_map[old_rId])

        # Also handle legacy v:imagedata elements (older Word format)
        for imgdata in new_element.iter("{urn:schemas-microsoft-com:vml}imagedata"):
            old_rId = imgdata.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}href")
            if old_rId and old_rId.startswith("rId") and old_rId in image_rel_map:
                imgdata.set("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}href", image_rel_map[old_rId])

        merged_doc.element.body.append(new_element)


def get_word_metadata(file_path: str) -> dict:
    """
    Return basic metadata for a .docx file.

    Args:
        file_path : Absolute path to the .docx file.

    Returns:
        Dictionary with file_name, file_size, paragraph_count, author, title, subject.
    """
    ok, msg = check_word_merge_deps()
    if not ok:
        raise RuntimeError(msg)

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    doc  = Document(file_path)
    core = doc.core_properties

    size_bytes = os.path.getsize(file_path)
    size_str   = (f"{size_bytes / 1_048_576:.2f} MB"
                  if size_bytes >= 1_048_576 else f"{size_bytes / 1024:.2f} KB")

    return {
        "file_name"       : os.path.basename(file_path),
        "file_size"       : size_str,
        "paragraph_count" : len(doc.paragraphs),
        "title"           : core.title   or "N/A",
        "author"          : core.author  or "N/A",
        "subject"         : core.subject or "N/A",
        "last_modified_by": core.last_modified_by or "N/A",
    }
