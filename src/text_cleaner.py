"""
src/text_cleaner.py
-------------------
Cleans and normalises raw text extracted from resumes.

The goal is to produce consistent, lowercase text that NLP algorithms
(TF-IDF, skill matching) can work with reliably, while preserving
meaningful technical terms such as programming language names and acronyms.
"""

import re


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Apply a full cleaning pipeline to raw resume text.

    Steps
    -----
    1. Convert to lowercase.
    2. Replace newlines and tabs with spaces.
    3. Remove URLs.
    4. Remove email addresses (already extracted in the parser stage).
    5. Remove phone numbers.
    6. Remove special characters except letters, numbers, +, # and spaces.
       (+ and # are kept for C++, C#, etc.)
    7. Collapse multiple spaces into one.
    8. Strip leading / trailing whitespace.

    Parameters
    ----------
    text : str
        Raw text extracted from a resume.

    Returns
    -------
    str
        Cleaned, normalised text.
    """
    if not text or not text.strip():
        return ""

    # Step 1 — Lowercase
    text = text.lower()

    # Step 2 — Replace newlines and tabs with a space
    text = re.sub(r"[\n\r\t]+", " ", text)

    # Step 3 — Remove URLs (http, https, www)
    text = re.sub(r"https?://\S+|www\.\S+", " ", text)

    # Step 4 — Remove email addresses
    text = re.sub(r"[a-z0-9._%+\-]+@[a-z0-9.\-]+\.[a-z]{2,}", " ", text)

    # Step 5 — Remove phone numbers (various formats)
    text = re.sub(r"(\+?\d{1,3}[\s\-]?)?(\(?\d{3}\)?[\s\-]?)(\d{3}[\s\-]?\d{4})", " ", text)

    # Step 6 — Keep only letters, digits, +, # and spaces
    # This preserves terms like c++, c#, f#, .net (dot removed but net kept)
    text = re.sub(r"[^a-z0-9+#\s]", " ", text)

    # Step 7 — Collapse multiple spaces
    text = re.sub(r"\s+", " ", text)

    # Step 8 — Strip
    return text.strip()


def normalize_skill_text(skill: str) -> str:
    """
    Lightly normalise a single skill string for comparison.
    Lowercases and strips whitespace only — does not remove + or #.

    Parameters
    ----------
    skill : str
        A skill name, e.g. 'Machine Learning', 'C++'.

    Returns
    -------
    str
        Lowercased, stripped skill string.
    """
    return skill.lower().strip()
