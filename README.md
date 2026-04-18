# 🗂 Advanced PDF Text Extractor & Merger System

A professional, feature-rich desktop application built with Python and Tkinter for extracting, searching, merging, and OCR-processing PDF files.

---

## ✨ Features

| Feature | Description |
|---|---|
| 📝 Text Extraction | High-quality text extraction using `pdfminer.six` |
| 🔀 PDF Merging | Merge multiple PDFs with optional page range selection |
| 🔍 Keyword Search | Search keyword across all loaded PDFs; results show page numbers |
| 🔬 OCR Support | Scanned/image PDF text recognition via Tesseract OCR |
| 💾 Export | Save extracted or OCR'd text to `.txt` file |
| ℹ Metadata | View file name, size, page count, author, and more |
| 📄 Page Ranges | Select specific pages like `1-3, 5, 7-9` for any operation |
| 🎨 Dark UI | Modern dark-themed Tkinter GUI with hover animations |

---

## 📁 Project Structure

```
pdfconverter/
├── main.py           # Entry point – boots the app with pre-flight checks
├── gui.py            # Full Tkinter UI: layout, buttons, panels, theme
├── pdf_utils.py      # PDF text extraction, merging, search, metadata
├── ocr_utils.py      # OCR via Tesseract + pdf2image
├── requirements.txt  # Python package dependencies
└── README.md         # This file
```

---

## 🛠 Setup Instructions

### Step 1 – Install Python (3.9 or higher)

Download from https://www.python.org/downloads/  
Verify: `python --version`

### Step 2 – Create a Virtual Environment (recommended)

```bash
python -m venv venv

# Activate on Windows:
venv\Scripts\activate

# Activate on macOS/Linux:
source venv/bin/activate
```

### Step 3 – Install Python Dependencies

```bash
pip install -r requirements.txt
```

### Step 4 – Install Tesseract OCR (for scanned PDFs)

> Skip this step if you don't need OCR — the rest of the app works without it.

#### Windows
1. Download the installer from:  
   https://github.com/UB-Mannheim/tesseract/wiki
2. Run the installer (default path: `C:\Program Files\Tesseract-OCR\`)
3. Optionally add `C:\Program Files\Tesseract-OCR\` to your system `PATH`  
   *(Control Panel → System → Advanced → Environment Variables → Path)*

**The `ocr_utils.py` already defaults to `C:\Program Files\Tesseract-OCR\tesseract.exe`.**  
If you install to a different location, update `DEFAULT_TESSERACT_CMD` in `ocr_utils.py`.

#### Additional language packs (optional)
During the Tesseract installation wizard, check the languages you want under  
*"Additional language data (download)"*.  
Then use the 3-letter ISO code in the **OCR Lang** field (e.g., `fra` for French).

#### macOS
```bash
brew install tesseract
```

#### Linux
```bash
sudo apt install tesseract-ocr
# Additional packs, e.g. Hindi:
sudo apt install tesseract-ocr-hin
```

---

### Step 5 – Install Poppler (required by pdf2image for OCR page rendering)

> Poppler renders PDF pages to images so Tesseract can read them.

#### Windows
1. Download the latest release from:  
   https://github.com/oschwartz10612/poppler-windows/releases
2. Extract the archive (e.g., to `C:\poppler\`)
3. Add `C:\poppler\Library\bin` to your system `PATH`  
   **-or-** pass `poppler_path=r"C:\poppler\Library\bin"` in `ocr_utils.perform_ocr()`.

#### macOS
```bash
brew install poppler
```

#### Linux
```bash
sudo apt install poppler-utils
```

---

## ▶️ Running the Application

```bash
python main.py
```

---

## 🧭 How to Use

### Upload PDFs
Click **📂 Upload PDF(s)** and select one or more `.pdf` files.  
Files appear in the left sidebar list.

### Extract Text
1. (Optional) Type a page range like `1-3, 5` in the **Page Range** field.
2. Click **📝 Extract Text**.  
   Text appears in the output box grouped by file and page.

### Merge PDFs
1. Load two or more PDFs.
2. (Optional) Set a page range to include only specific pages from each file.
3. (Optional) Set a custom output filename in **Merge Output Filename**.
4. Click **🔀 Merge PDFs** and choose where to save.

### Search Keyword
1. Type a word or phrase in the **🔍 Keyword** field.
2. Optionally tick **Case-sensitive**.
3. Click **🔍 Search Keyword** or press `Enter` in the keyword box.  
   Results show which page numbers each file contains the keyword.

### Apply OCR (Scanned PDFs)
1. Make sure Tesseract and Poppler are installed (see above).
2. Set the **OCR Lang** field (default `eng`).
3. (Optional) Set a page range.
4. Click **🔬 Apply OCR**.  
   OCR-extracted text appears in the output box with page separators.

### Save Text
Click **💾 Save Text** to export whatever is in the output box to a `.txt` file.

### View Metadata
- Click **ℹ View Metadata** in the sidebar, or  
- **Double-click** any file in the list.

---

## 🧩 Module Reference

### `main.py`
- Checks Python ≥ 3.9 and required packages on startup.
- Enables Windows high-DPI awareness.
- Instantiates `PDFConverterApp` and starts the Tkinter event loop.

### `gui.py` — `PDFConverterApp`
| Method | Purpose |
|---|---|
| `upload_pdfs()` | Opens file dialog, adds PDFs to the list |
| `extract_text()` | Calls `pdf_utils.extract_text_from_pdf()` per file in a thread |
| `merge_pdfs()` | Calls `pdf_utils.merge_pdfs()` with optional per-file page ranges |
| `search_keyword()` | Calls `pdf_utils.search_keyword_in_pdfs()` and formats results |
| `apply_ocr()` | Calls `ocr_utils.perform_ocr()` with progress callback |
| `save_text()` | Writes the output box content to a `.txt` file |
| `show_metadata()` | Displays `pdf_utils.get_pdf_metadata()` in the output box |

> All blocking operations run in daemon threads (`@run_in_thread` decorator)  
> so the GUI stays responsive during processing.

### `pdf_utils.py`
| Function | Description |
|---|---|
| `extract_text_from_pdf(path, page_range)` | Uses `pdfminer.six` to extract selectable text per page |
| `merge_pdfs(paths, output, page_ranges)` | Uses `PyPDF2.PdfWriter` to merge PDFs |
| `search_keyword_in_pdfs(paths, keyword)` | Page-by-page keyword regex search |
| `get_pdf_metadata(path)` | Returns file size, page count, title, author, etc. |
| `_parse_page_range(str)` | Parses `"1-3, 5, 7-9"` → `[1, 2, 3, 5, 7, 8, 9]` |

### `ocr_utils.py`
| Function | Description |
|---|---|
| `is_ocr_available()` | Checks pytesseract, pdf2image, Pillow, Tesseract binary |
| `configure_tesseract(path)` | Points pytesseract at the Tesseract binary |
| `perform_ocr(path, page_range, dpi, lang, callback)` | Full OCR pipeline with progress callbacks |
| `get_available_languages()` | Lists installed Tesseract language packs |

---

## 🧪 Sample Usage (CLI Testing)

```python
# Quick test without the GUI
import pdf_utils, ocr_utils

# Extract text
text = pdf_utils.extract_text_from_pdf("sample.pdf", page_range="1-2")
print(text)

# Get metadata
meta = pdf_utils.get_pdf_metadata("sample.pdf")
print(meta)

# Merge
pdf_utils.merge_pdfs(["a.pdf", "b.pdf"], "merged.pdf", {"a.pdf": "1-3"})

# Search
results = pdf_utils.search_keyword_in_pdfs(["doc.pdf"], "invoice")
# Returns: {"doc.pdf": [1, 4, 7]}

# OCR
text = ocr_utils.perform_ocr("scanned.pdf", page_range="1", lang="eng")
print(text)
```

---

## 🔮 Optional Improvements

| Idea | Description |
|---|---|
| 📌 Drag-and-drop | Use `tkinterdnd2` to allow dragging PDFs directly onto the file list |
| 🔐 Password-protected PDFs | Pass `password=` to `PdfReader` |
| 📊 Word frequency chart | Visualise top words using `matplotlib` embedded in Tkinter |
| 🌐 Multi-language UI | Detect and auto-select OCR language based on file metadata |
| 📑 Table extraction | Add `camelot-py` or `pdfplumber` for structured table extraction |
| 🗜 PDF Compression | Reduce file size using `pikepdf` |
| 🌓 Light/dark theme toggle | Add a toggle button to switch colour palette at runtime |
| 🔖 Bookmark support | List and navigate by PDF bookmarks using `PyPDF2` |

---

## ❗ Known Limitations

- Pdfminer cannot extract text from **scanned / image-only** PDFs — use OCR.
- OCR accuracy depends on image resolution and Tesseract language packs installed.
- Very large PDFs (500+ pages) may take time; the progress bar gives feedback.
- Encrypted/password-protected PDFs are not yet supported in this version.

---

## 📄 License

MIT — free to use, modify, and distribute.
#   S t r u c t u r a P D F  
 