"""
main.py
-------
Command-line interface for the Automated Resume Screening Tool.

Run this file to perform resume screening without the Streamlit dashboard:

    python main.py

The application will:
  1. Display a welcome message.
  2. Accept a job description (or load sample data).
  3. Accept required skills.
  4. Process all resumes in the resumes/ folder.
  5. Display ranked results.
  6. Generate a CSV report in outputs/.
"""

import os
import sys

# Add the project root to the Python path so src/ imports work correctly.
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.screening_engine  import screen_resumes_from_folder, validate_inputs
from src.report_generator  import generate_csv_report, generate_summary_report
from src.candidate_ranker  import build_ranking_summary


# ---------------------------------------------------------------------------
# Default sample data (used when user presses Enter without typing)
# ---------------------------------------------------------------------------

SAMPLE_JD = (
    "We are looking for a skilled Data Scientist with experience in Python, "
    "machine learning, and natural language processing. The candidate should "
    "be proficient in Pandas, NumPy, and Scikit-learn for data analysis and "
    "model building. Experience with SQL databases and data visualisation tools "
    "is required. Strong communication and problem-solving skills are essential."
)

SAMPLE_SKILLS = [
    "Python", "Machine Learning", "Pandas", "NumPy",
    "Scikit-learn", "SQL", "NLP", "Communication", "Problem Solving",
]

DEFAULT_RESUME_FOLDER = os.path.join(PROJECT_ROOT, "resumes")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def print_banner():
    print("\n" + "=" * 50)
    print("   AUTOMATED RESUME SCREENING TOOL")
    print("   Educational ATS Simulation")
    print("=" * 50)
    print("\nWelcome to the Automated Resume Screening Tool!")
    print("This tool ranks candidates based on job requirements.\n")


def print_separator():
    print("-" * 50)


def print_results(ranked_candidates: list[dict], summary: dict):
    """Display ranked results in a formatted table."""

    print("\n" + "=" * 50)
    print("  SCREENING RESULTS")
    print("=" * 50)

    print(f"\n  Total candidates processed : {summary.get('total', 0)}")
    print(f"  Shortlisted                : {summary.get('shortlisted', 0)}")
    print(f"  Manual review              : {summary.get('manual_review', 0)}")
    print(f"  Not shortlisted            : {summary.get('not_shortlisted', 0)}")
    print(f"  Top candidate              : {summary.get('top_candidate', 'N/A')}")
    print(f"  Average score              : {summary.get('average_score', 0.0):.1f}%")

    print("\n" + "-" * 50)
    print(f"  {'RANK':<5} {'NAME':<20} {'SCORE':>6}  {'RECOMMENDATION'}")
    print("-" * 50)

    for c in ranked_candidates:
        name  = c.get("name", "Unknown")[:19]
        score = c.get("final_score", 0.0)
        rec   = c.get("recommendation", "N/A")
        rank  = c.get("rank", "-")
        print(f"  {rank:<5} {name:<20} {score:>5.1f}%  {rec}")

    print("-" * 50)

    # Detailed view
    print("\n" + "=" * 50)
    print("  DETAILED CANDIDATE BREAKDOWN")
    print("=" * 50)

    for c in ranked_candidates:
        print(f"\n  Rank #{c.get('rank')} — {c.get('name', 'Unknown')}")
        print(f"    Email       : {c.get('email', 'Not found')}")
        print(f"    Phone       : {c.get('phone', 'Not found')}")
        print(f"    File        : {c.get('filename', '')}")
        print(f"    Skills found: {', '.join(c.get('extracted_skills', [])) or 'None'}")
        print(f"    Matched     : {', '.join(c.get('matched_skills', [])) or 'None'}")
        print(f"    Missing     : {', '.join(c.get('missing_skills', [])) or 'None'}")
        print(f"    Skill score : {c.get('skill_score', 0):.1f}%")
        print(f"    JD similarity: {c.get('similarity_score', 0):.1f}%")
        exp = c.get("experience_score")
        edu = c.get("education_score")
        exp_str = f"{exp:.1f}%" if exp is not None else "Not Assessed"
        edu_str = f"{edu:.1f}%" if edu is not None else "Not Assessed"
        print(f"    Experience  : {exp_str} — {c.get('experience_reason', '')}")
        print(f"    Education   : {edu_str} — {c.get('education_reason', '')}")
        print(f"    FINAL SCORE : {c.get('final_score', 0):.1f}%")
        print(f"    RECOMMENDATION: {c.get('recommendation', 'N/A')}")
        print_separator()

    print("\n  NOTE: Recommendations are for guidance only and require human review.")


# ---------------------------------------------------------------------------
# User input helpers
# ---------------------------------------------------------------------------

def get_job_description() -> str:
    print("\n--- STEP 1: Job Description ---")
    print("Enter the job description below.")
    print("(Press Enter without typing to use the built-in sample JD)\n")
    try:
        jd = input("Job description: ").strip()
    except EOFError:
        jd = ""
    if not jd:
        print("  [INFO] Using sample job description.")
        return SAMPLE_JD
    return jd


def get_required_skills() -> list[str]:
    print("\n--- STEP 2: Required Skills ---")
    print("Enter required skills separated by commas.")
    print("Example: Python, Machine Learning, SQL, Pandas")
    print("(Press Enter without typing to use the built-in sample skills)\n")
    try:
        raw = input("Required skills: ").strip()
    except EOFError:
        raw = ""
    if not raw:
        print("  [INFO] Using sample required skills:")
        print("  " + ", ".join(SAMPLE_SKILLS))
        return SAMPLE_SKILLS
    return [s.strip() for s in raw.split(",") if s.strip()]


def get_resume_folder() -> str:
    print("\n--- STEP 3: Resume Folder ---")
    print(f"Default folder: {DEFAULT_RESUME_FOLDER}")
    print("(Press Enter to use the default resumes/ folder)\n")
    try:
        path = input("Resume folder path: ").strip()
    except EOFError:
        path = ""
    if not path:
        return DEFAULT_RESUME_FOLDER
    return path


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    print_banner()

    # Collect inputs
    job_description  = get_job_description()
    required_skills  = get_required_skills()
    resume_folder    = get_resume_folder()

    # Validate
    errors = validate_inputs(job_description, required_skills, resume_folder)
    if errors:
        print("\n[VALIDATION ERRORS]")
        for err in errors:
            print(f"  - {err}")
        sys.exit(1)

    # Run screening pipeline
    ranked_candidates, summary = screen_resumes_from_folder(
        resume_folder   = resume_folder,
        job_description = job_description,
        required_skills = required_skills,
    )

    if not ranked_candidates:
        print("\n[ERROR] No candidates were processed. Exiting.")
        sys.exit(1)

    # Display results
    print_results(ranked_candidates, summary)

    # Generate CSV reports
    print("\n--- GENERATING REPORTS ---")
    try:
        report_path  = generate_csv_report(ranked_candidates)
        summary_path = generate_summary_report(summary)
        print(f"\n  Screening report  : {report_path}")
        print(f"  Summary report    : {summary_path}")
    except Exception as e:
        print(f"\n  [ERROR] Report generation failed: {e}")

    print("\n========================================")
    print("  Screening complete. Thank you!")
    print("  Review recommendations with a recruiter.")
    print("========================================\n")


if __name__ == "__main__":
    main()
