"""
src/resume_parser.py
--------------------
Handles text extraction from PDF, DOCX, and TXT resume files.
Also extracts basic candidate information (name, email, phone)
using regular expressions.

Supported formats : PDF (.pdf), Word (.docx), Plain text (.txt)
Dependencies      : pdfplumber, python-docx
"""

import os
import re
import pdfplumber
from docx import Document


# ---------------------------------------------------------------------------
# Text extraction functions
# ---------------------------------------------------------------------------

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extract all text from a PDF file using pdfplumber.

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the PDF file.

    Returns
    -------
    str
        Extracted text, or an empty string if extraction fails.
    """
    text = ""
    try:
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:                       # skip blank pages
                    text += page_text + "\n"
    except FileNotFoundError:
        print(f"  [ERROR] PDF not found: {file_path}")
    except Exception as e:
        print(f"  [ERROR] Could not read PDF '{os.path.basename(file_path)}': {e}")

    return text.strip()


def extract_text_from_docx(file_path: str) -> str:
    """
    Extract all paragraph text from a DOCX file using python-docx.

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the DOCX file.

    Returns
    -------
    str
        Extracted text, or an empty string if extraction fails.
    """
    text = ""
    try:
        doc = Document(file_path)
        paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]
        text = "\n".join(paragraphs)
    except FileNotFoundError:
        print(f"  [ERROR] DOCX not found: {file_path}")
    except Exception as e:
        print(f"  [ERROR] Could not read DOCX '{os.path.basename(file_path)}': {e}")

    return text.strip()


def extract_text_from_txt(file_path: str) -> str:
    """
    Read all text from a plain TXT file.

    Tries UTF-8 first, falls back to latin-1 to handle most encodings.

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the TXT file.

    Returns
    -------
    str
        File contents, or an empty string if reading fails.
    """
    text = ""
    for encoding in ("utf-8", "latin-1"):
        try:
            with open(file_path, "r", encoding=encoding) as f:
                text = f.read()
            break                                   # stop if successful
        except FileNotFoundError:
            print(f"  [ERROR] TXT not found: {file_path}")
            break
        except UnicodeDecodeError:
            continue                                # try next encoding
        except Exception as e:
            print(f"  [ERROR] Could not read TXT '{os.path.basename(file_path)}': {e}")
            break

    return text.strip()


def extract_text(file_path: str) -> str:
    """
    Route a resume file to the correct extractor based on file extension.

    Parameters
    ----------
    file_path : str
        Path to the resume file (.pdf, .docx, or .txt).

    Returns
    -------
    str
        Extracted raw text, or an empty string on failure.
    """
    if not os.path.isfile(file_path):
        print(f"  [ERROR] File does not exist: {file_path}")
        return ""

    ext = os.path.splitext(file_path)[1].lower()

    if ext == ".pdf":
        return extract_text_from_pdf(file_path)
    elif ext == ".docx":
        return extract_text_from_docx(file_path)
    elif ext == ".txt":
        return extract_text_from_txt(file_path)
    else:
        print(f"  [WARNING] Unsupported file format: '{ext}' — {os.path.basename(file_path)}")
        return ""


# ---------------------------------------------------------------------------
# Candidate information extraction
# ---------------------------------------------------------------------------

def extract_email(text: str) -> str:
    """Return the first email address found in text, or 'Not found'."""
    pattern = r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"
    match = re.search(pattern, text)
    return match.group(0) if match else "Not found"


def extract_phone(text: str) -> str:
    """
    Return the first phone number found in text, or 'Not found'.
    Handles common formats: +91-9876543210, (123) 456-7890, 1234567890, etc.
    """
    pattern = r"(\+?\d{1,3}[\s\-]?)?(\(?\d{3}\)?[\s\-]?)(\d{3}[\s\-]?\d{4})"
    match = re.search(pattern, text)
    return match.group(0).strip() if match else "Not found"


def extract_name(text: str) -> str:
    """
    Attempt to extract a candidate name from the first non-empty lines
    of the resume text.

    Strategy: the first line that looks like a proper name
    (two or three title-cased words, no special characters) is returned.

    Parameters
    ----------
    text : str
        Raw resume text.

    Returns
    -------
    str
        Extracted name, or 'Not found'.
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    for line in lines[:6]:                          # check only the first 6 lines
        # A name: 2-4 words, each starting with a capital letter
        if re.match(r"^[A-Z][a-z]+(\s[A-Z][a-z]+){1,3}$", line):
            return line
    return "Not found"


def parse_resume(file_path: str) -> dict:
    """
    Full pipeline: extract text from a resume file and pull out
    candidate metadata.

    Parameters
    ----------
    file_path : str
        Path to the resume file.

    Returns
    -------
    dict
        {
            'filename'  : str,
            'raw_text'  : str,
            'name'      : str,
            'email'     : str,
            'phone'     : str,
            'has_text'  : bool
        }
    """
    filename = os.path.basename(file_path)
    raw_text = extract_text(file_path)

    if not raw_text:
        print(f"  [WARNING] No text extracted from: {filename}")
        return {
            "filename" : filename,
            "raw_text" : "",
            "name"     : "Unknown",
            "email"    : "Not found",
            "phone"    : "Not found",
            "has_text" : False,
        }

    return {
        "filename" : filename,
        "raw_text" : raw_text,
        "name"     : extract_name(raw_text),
        "email"    : extract_email(raw_text),
        "phone"    : extract_phone(raw_text),
        "has_text" : True,
    }


def load_resumes_from_folder(folder_path: str) -> list[dict]:
    """
    Load and parse every supported resume in a folder.

    Parameters
    ----------
    folder_path : str
        Path to the folder containing resume files.

    Returns
    -------
    list[dict]
        List of parsed resume dictionaries (one per file).
    """
    supported_extensions = {".pdf", ".docx", ".txt"}

    if not os.path.isdir(folder_path):
        print(f"  [ERROR] Folder not found: {folder_path}")
        return []

    files = [
        os.path.join(folder_path, f)
        for f in os.listdir(folder_path)
        if os.path.splitext(f)[1].lower() in supported_extensions
    ]

    if not files:
        print(f"  [WARNING] No supported resume files found in: {folder_path}")
        return []

    print(f"  Found {len(files)} resume(s) in '{folder_path}'")
    results = []
    for file_path in files:
        print(f"  Parsing: {os.path.basename(file_path)}")
        parsed = parse_resume(file_path)
        results.append(parsed)

    return results
