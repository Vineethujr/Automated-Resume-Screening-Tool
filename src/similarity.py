"""
src/similarity.py
-----------------
Computes TF-IDF cosine similarity between a resume and a job description.

TF-IDF (Term Frequency – Inverse Document Frequency) converts text into
numerical vectors where words that appear frequently in a document but rarely
across all documents get higher weights.

Cosine Similarity measures the angle between two TF-IDF vectors:
  - 1.0 (100%) = identical text direction (maximum match)
  - 0.0  (0%) = completely unrelated text

Both come from scikit-learn.
"""

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def calculate_similarity(resume_text: str, job_description: str) -> float:
    """
    Calculate the cosine similarity between a resume and a job description
    using TF-IDF vectorisation.

    Parameters
    ----------
    resume_text : str
        Cleaned text from a candidate's resume.
    job_description : str
        Cleaned job description text.

    Returns
    -------
    float
        Similarity score in the range 0.0 – 100.0 (percentage).
        Returns 0.0 if either input is empty or no vocabulary is found.
    """
    # Guard: both inputs must have content
    if not resume_text or not resume_text.strip():
        return 0.0
    if not job_description or not job_description.strip():
        return 0.0

    try:
        # TF-IDF vectoriser — ignore very common English stop words
        vectorizer = TfidfVectorizer(stop_words="english")

        # Fit on both documents together so the vocabulary is shared
        tfidf_matrix = vectorizer.fit_transform([resume_text, job_description])

        # cosine_similarity returns a 2D matrix; [0][1] is resume vs JD
        score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

        # Convert to percentage and clamp to [0, 100]
        return float(round(min(max(score * 100, 0.0), 100.0), 2))

    except ValueError:
        # Raised by TfidfVectorizer when the vocabulary is empty
        # (e.g., input contains only stop words)
        return 0.0
    except Exception as e:
        print(f"  [ERROR] Similarity calculation failed: {e}")
        return 0.0


def calculate_batch_similarity(
    resume_texts: list[str],
    job_description: str,
) -> list[float]:
    """
    Calculate similarity scores for multiple resumes against a single
    job description in one vectorisation pass (more efficient than
    calling calculate_similarity repeatedly).

    Parameters
    ----------
    resume_texts : list[str]
        List of cleaned resume texts.
    job_description : str
        Cleaned job description text.

    Returns
    -------
    list[float]
        Similarity scores (0.0 – 100.0) corresponding to each resume.
    """
    if not job_description or not job_description.strip():
        return [0.0] * len(resume_texts)

    if not resume_texts:
        return []

    try:
        # Put the JD first, then all resumes
        documents = [job_description] + resume_texts

        vectorizer = TfidfVectorizer(stop_words="english")
        tfidf_matrix = vectorizer.fit_transform(documents)

        # JD vector is row 0; resume vectors are rows 1..n
        jd_vector      = tfidf_matrix[0:1]
        resume_vectors = tfidf_matrix[1:]

        scores = cosine_similarity(resume_vectors, jd_vector).flatten()

        return [float(round(min(max(s * 100, 0.0), 100.0), 2)) for s in scores]

    except ValueError:
        return [0.0] * len(resume_texts)
    except Exception as e:
        print(f"  [ERROR] Batch similarity failed: {e}")
        return [0.0] * len(resume_texts)
