"""
src/report_generator.py
-----------------------
Generates a CSV screening report from ranked candidate results and saves
it to the outputs/ directory.

Each report filename includes a timestamp so previous reports are never
accidentally overwritten.

Output columns
--------------
  Rank, Name, Email, Phone, Filename,
  Extracted Skills, Matched Skills, Missing Skills,
  Skill Score, Similarity Score, Experience Score, Education Score,
  Final Score, Recommendation, Score Basis,
  Experience Notes, Education Notes

"Not Assessed" is written in the Experience/Education score cells when
those components could not be evaluated from the resume text.  Their
weights are excluded from the final score; the Score Basis column
explains exactly which components were used.
"""

import os
import csv
from datetime import datetime


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

OUTPUTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),   # project root
    "outputs",
)

REPORT_COLUMNS = [
    "Rank",
    "Name",
    "Email",
    "Phone",
    "Filename",
    "Extracted Skills",
    "Matched Skills",
    "Missing Skills",
    "Skill Score (%)",
    "Similarity Score (%)",
    "Experience Score (%)",
    "Education Score (%)",
    "Final Score (%)",
    "Recommendation",
    "Score Basis",
    "Experience Notes",
    "Education Notes",
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_report_filename() -> str:
    """Return a timestamped CSV filename, e.g. screening_report_20240315_142530.csv"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"screening_report_{timestamp}.csv"


def _list_to_str(items) -> str:
    """Convert a list to a semicolon-separated string for CSV cells."""
    if not items:
        return "None"
    if isinstance(items, list):
        return "; ".join(str(i) for i in items)
    return str(items)


def _fmt_score(value) -> str:
    """
    Format a score value for the CSV.

    Returns "Not Assessed" when value is None, otherwise the numeric value
    formatted to two decimal places.
    """
    if value is None:
        return "Not Assessed"
    return str(round(float(value), 2))


def _build_row(candidate: dict) -> dict:
    """
    Map a ranked candidate dictionary to a flat CSV row dictionary.

    Experience and education scores of None are written as "Not Assessed".
    The Score Basis column explains which components contributed to the
    final score.
    """
    return {
        "Rank"                  : candidate.get("rank", "N/A"),
        "Name"                  : candidate.get("name", "Unknown"),
        "Email"                 : candidate.get("email", "Not found"),
        "Phone"                 : candidate.get("phone", "Not found"),
        "Filename"              : candidate.get("filename", ""),
        "Extracted Skills"      : _list_to_str(candidate.get("extracted_skills", [])),
        "Matched Skills"        : _list_to_str(candidate.get("matched_skills", [])),
        "Missing Skills"        : _list_to_str(candidate.get("missing_skills", [])),
        "Skill Score (%)"       : _fmt_score(candidate.get("skill_score")),
        "Similarity Score (%)"  : _fmt_score(candidate.get("similarity_score")),
        "Experience Score (%)"  : _fmt_score(candidate.get("experience_score")),   # may be None
        "Education Score (%)"   : _fmt_score(candidate.get("education_score")),    # may be None
        "Final Score (%)"       : _fmt_score(candidate.get("final_score")),
        "Recommendation"        : candidate.get("recommendation", "N/A"),
        "Score Basis"           : candidate.get("score_basis", ""),
        "Experience Notes"      : candidate.get("experience_reason", ""),
        "Education Notes"       : candidate.get("education_reason", ""),
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_csv_report(
    ranked_candidates : list[dict],
    output_dir        : str = OUTPUTS_DIR,
    filename          : str | None = None,
) -> str:
    """
    Write a CSV screening report for all ranked candidates.

    Parameters
    ----------
    ranked_candidates : list[dict]
        Output of candidate_ranker.rank_candidates().
    output_dir : str
        Directory where the CSV will be saved. Created if it does not exist.
    filename : str, optional
        Custom filename. If None, a timestamped name is generated.

    Returns
    -------
    str
        Absolute path to the generated CSV file.

    Raises
    ------
    ValueError
        If ranked_candidates is empty.
    IOError
        If the file cannot be written.
    """
    if not ranked_candidates:
        raise ValueError("No candidate data to write — report not generated.")

    os.makedirs(output_dir, exist_ok=True)

    report_filename = filename or _build_report_filename()
    output_path = os.path.join(output_dir, report_filename)

    try:
        with open(output_path, "w", newline="", encoding="utf-8") as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=REPORT_COLUMNS)
            writer.writeheader()
            for candidate in ranked_candidates:
                writer.writerow(_build_row(candidate))

        print(f"  [OK] Report saved: {output_path}")
        return output_path

    except IOError as e:
        raise IOError(f"Failed to write report to '{output_path}': {e}") from e


def generate_summary_report(summary: dict, output_dir: str = OUTPUTS_DIR) -> str:
    """
    Write a one-row CSV summary of the overall screening session.

    Parameters
    ----------
    summary : dict
        Output of candidate_ranker.build_ranking_summary().
    output_dir : str
        Directory where the CSV will be saved.

    Returns
    -------
    str
        Absolute path to the summary CSV file.
    """
    os.makedirs(output_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = os.path.join(output_dir, f"summary_report_{timestamp}.csv")

    columns = [
        "Total Candidates", "Shortlisted", "Manual Review",
        "Not Shortlisted", "Top Candidate", "Average Score (%)",
    ]
    row = {
        "Total Candidates"  : summary.get("total", 0),
        "Shortlisted"       : summary.get("shortlisted", 0),
        "Manual Review"     : summary.get("manual_review", 0),
        "Not Shortlisted"   : summary.get("not_shortlisted", 0),
        "Top Candidate"     : summary.get("top_candidate", "N/A"),
        "Average Score (%)" : summary.get("average_score", 0.0),
    }

    try:
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=columns)
            writer.writeheader()
            writer.writerow(row)
        print(f"  [OK] Summary saved: {path}")
        return path
    except IOError as e:
        raise IOError(f"Failed to write summary: {e}") from e
