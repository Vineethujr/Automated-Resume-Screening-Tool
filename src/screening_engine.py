"""
src/screening_engine.py
-----------------------
Central orchestration module for the Automated Resume Screening Tool.

This module coordinates all other modules in the correct pipeline order:

  1. Load resumes from folder / uploaded file bytes.
  2. Extract text (PDF / DOCX / TXT).
  3. Clean text.
  4. Extract candidate info (name, email, phone).
  5. Extract skills.
  6. Match skills against job requirements.
  7. Compute TF-IDF cosine similarity.
  8. Calculate weighted final scores.
  9. Rank candidates.
  10. Attach recommendations.

Returns a list of fully enriched candidate dictionaries ready for
the report generator or the Streamlit dashboard.
"""

import os
import io
import tempfile

from src.resume_parser    import parse_resume, load_resumes_from_folder
from src.text_cleaner     import clean_text
from src.skill_extractor  import extract_skills, match_required_skills
from src.similarity       import calculate_batch_similarity
from src.score_calculator import calculate_final_score, DEFAULT_WEIGHTS
from src.candidate_ranker import rank_candidates, build_ranking_summary


# ---------------------------------------------------------------------------
# Main pipeline entry points
# ---------------------------------------------------------------------------

def screen_resumes_from_folder(
    resume_folder    : str,
    job_description  : str,
    required_skills  : list[str],
    weights          : dict | None = None,
    shortlist_threshold : float = 60.0,
    review_threshold    : float = 40.0,
) -> tuple[list[dict], dict]:
    """
    Run the complete screening pipeline on all resumes inside a folder.

    Parameters
    ----------
    resume_folder : str
        Path to the folder containing resume files.
    job_description : str
        Raw text of the job description.
    required_skills : list[str]
        List of required skill names for the position.
    weights : dict, optional
        Custom scoring weights (see score_calculator.DEFAULT_WEIGHTS).
    shortlist_threshold : float
        Score threshold for shortlisting (default 60).
    review_threshold : float
        Score threshold for manual review (default 40).

    Returns
    -------
    tuple[list[dict], dict]
        (ranked_candidates, summary)
        ranked_candidates : one dict per candidate (fully enriched).
        summary           : high-level counts from build_ranking_summary().
    """
    print("\n" + "=" * 50)
    print("  AUTOMATED RESUME SCREENING TOOL")
    print("=" * 50)

    # --- Step 1: Load resumes ---
    print("\n[1/6] Loading resumes...")
    parsed_resumes = load_resumes_from_folder(resume_folder)

    if not parsed_resumes:
        print("  [ERROR] No resumes found. Screening aborted.")
        return [], {}

    # Filter out resumes with no text
    valid_resumes = [r for r in parsed_resumes if r["has_text"]]
    skipped       = len(parsed_resumes) - len(valid_resumes)
    if skipped:
        print(f"  [WARNING] {skipped} resume(s) had no extractable text and were skipped.")
    if not valid_resumes:
        print("  [ERROR] None of the resumes contained extractable text.")
        return [], {}

    # --- Step 2: Clean texts ---
    print(f"\n[2/6] Cleaning text for {len(valid_resumes)} resume(s)...")
    clean_jd = clean_text(job_description)
    for r in valid_resumes:
        r["clean_text"] = clean_text(r["raw_text"])

    # --- Step 3: TF-IDF similarity (batch) ---
    print("\n[3/6] Calculating TF-IDF similarity scores...")
    resume_texts  = [r["clean_text"] for r in valid_resumes]
    similarity_scores = calculate_batch_similarity(resume_texts, clean_jd)

    # --- Step 4: Skill extraction + matching ---
    print("\n[4/6] Extracting and matching skills...")
    for r, sim_score in zip(valid_resumes, similarity_scores):
        r["similarity_score"] = sim_score
        # Use raw text for skill extraction (preserves original casing / symbols)
        r["extracted_skills"] = extract_skills(r["raw_text"])
        skill_match = match_required_skills(r["extracted_skills"], required_skills)
        r.update(skill_match)   # adds matched_skills, missing_skills, skill_match_pct

    # --- Step 5: Score calculation ---
    print("\n[5/6] Calculating final scores...")
    for r in valid_resumes:
        scores = calculate_final_score(
            skill_match_pct  = r["skill_match_pct"],
            similarity_score = r["similarity_score"],
            resume_text      = r["raw_text"],
            weights          = weights,
        )
        r.update(scores)    # adds skill_score, experience_score, education_score, final_score

    # --- Step 6: Rank candidates ---
    print("\n[6/6] Ranking candidates...")
    ranked = rank_candidates(valid_resumes, shortlist_threshold, review_threshold)
    summary = build_ranking_summary(ranked)

    print(f"\n  Screening complete. {len(ranked)} candidate(s) processed.")
    return ranked, summary


def screen_resumes_from_uploads(
    uploaded_files   : list,
    job_description  : str,
    required_skills  : list[str],
    weights          : dict | None = None,
    shortlist_threshold : float = 60.0,
    review_threshold    : float = 40.0,
) -> tuple[list[dict], dict]:
    """
    Run the screening pipeline on uploaded file objects (Streamlit use case).

    Uploaded files are written to a temporary directory and then processed
    through the standard folder-based pipeline.

    Parameters
    ----------
    uploaded_files : list
        List of Streamlit UploadedFile objects (or any file-like objects
        with .name and .read() attributes).
    job_description : str
        Raw text of the job description.
    required_skills : list[str]
        List of required skill names for the position.
    weights : dict, optional
        Custom scoring weights.
    shortlist_threshold : float
    review_threshold    : float

    Returns
    -------
    tuple[list[dict], dict]
        (ranked_candidates, summary)
    """
    if not uploaded_files:
        return [], {}

    supported = {".pdf", ".docx", ".txt"}

    # Write uploaded files to a temp directory
    with tempfile.TemporaryDirectory() as tmp_dir:
        for uploaded_file in uploaded_files:
            name = uploaded_file.name
            ext  = os.path.splitext(name)[1].lower()
            if ext not in supported:
                print(f"  [WARNING] Skipping unsupported file: {name}")
                continue
            dest = os.path.join(tmp_dir, name)
            with open(dest, "wb") as f:
                f.write(uploaded_file.read())

        return screen_resumes_from_folder(
            resume_folder       = tmp_dir,
            job_description     = job_description,
            required_skills     = required_skills,
            weights             = weights,
            shortlist_threshold = shortlist_threshold,
            review_threshold    = review_threshold,
        )


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------

def validate_inputs(
    job_description  : str,
    required_skills  : list[str],
    resume_folder    : str = "",
) -> list[str]:
    """
    Validate screening inputs before running the pipeline.

    Returns
    -------
    list[str]
        List of error messages (empty list = all inputs valid).
    """
    errors = []

    if not job_description or not job_description.strip():
        errors.append("Job description is empty. Please provide a job description.")

    if not required_skills:
        errors.append("Required skills list is empty. Please specify at least one skill.")

    if resume_folder and not os.path.isdir(resume_folder):
        errors.append(f"Resume folder not found: '{resume_folder}'")

    return errors
