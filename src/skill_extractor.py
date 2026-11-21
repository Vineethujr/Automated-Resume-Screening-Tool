"""
src/skill_extractor.py
----------------------
Extracts technical and soft skills from resume text by matching against
a predefined skill dictionary.

Design decisions
----------------
* Skills are matched using whole-word boundaries (\\b) to prevent false
  positives.  For example, the letter "C" will not match inside the word
  "communication" or "scikit".
* The skill "C" uses a stricter pattern so it only matches the standalone
  programming language name and not every occurrence of the character.
* Matching is case-insensitive (the cleaned text is already lowercase, but
  the patterns are compiled with re.IGNORECASE for safety).
"""

import re
from src.text_cleaner import normalize_skill_text


# ---------------------------------------------------------------------------
# Predefined skill dictionary
# ---------------------------------------------------------------------------

SKILL_CATEGORIES: dict[str, list[str]] = {
    "Programming Languages": [
        "Python", "Java", "JavaScript", "C++", "C#", "C",
        "R", "Go", "Swift", "Kotlin", "TypeScript", "PHP", "Ruby",
    ],
    "Data Analysis": [
        "Pandas", "NumPy", "Excel", "SQL", "Power BI", "Tableau",
        "Matplotlib", "Seaborn", "SPSS", "SAS",
    ],
    "Machine Learning / AI": [
        "Machine Learning", "Deep Learning", "NLP",
        "Natural Language Processing", "Computer Vision",
        "Scikit-learn", "TensorFlow", "Keras", "PyTorch", "OpenCV",
    ],
    "Web Development": [
        "HTML", "CSS", "Flask", "Django", "Streamlit",
        "React", "Node.js", "FastAPI", "Bootstrap",
    ],
    "Databases": [
        "MySQL", "PostgreSQL", "MongoDB", "SQLite", "Oracle",
        "Firebase", "Redis",
    ],
    "Cloud & DevOps": [
        "AWS", "Azure", "GCP", "Docker", "Kubernetes",
        "Git", "GitHub", "CI/CD", "Linux",
    ],
    "Soft Skills": [
        "Communication", "Problem Solving", "Teamwork",
        "Leadership", "Critical Thinking", "Time Management",
        "Adaptability", "Collaboration",
    ],
}

# Flat list of all skills (used for quick lookup)
ALL_SKILLS: list[str] = [
    skill
    for skills in SKILL_CATEGORIES.values()
    for skill in skills
]


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_pattern(skill: str) -> re.Pattern:
    """
    Compile a regex pattern for a skill with word-boundary anchors.

    Special cases
    -------------
    * "C"  → matched only when surrounded by spaces or at string edges,
              not as a substring of a word.
    * "C++" / "C#" → escaped properly so + and # are literal.

    Parameters
    ----------
    skill : str
        Skill name as written in SKILL_CATEGORIES.

    Returns
    -------
    re.Pattern
        Compiled pattern.
    """
    escaped = re.escape(skill)

    # For single-letter "C" use a stricter boundary
    if skill.strip().upper() == "C":
        return re.compile(r"(?<![a-zA-Z+#])c(?![a-zA-Z+#0-9])", re.IGNORECASE)

    return re.compile(r"\b" + escaped + r"\b", re.IGNORECASE)


# Pre-compile all patterns once at import time (performance optimisation)
_SKILL_PATTERNS: dict[str, re.Pattern] = {
    skill: _build_pattern(skill) for skill in ALL_SKILLS
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_skills(text: str) -> list[str]:
    """
    Find all known skills present in the given text.

    Parameters
    ----------
    text : str
        Cleaned or raw resume text.

    Returns
    -------
    list[str]
        Unique list of matched skill names (original casing from the
        skill dictionary).
    """
    if not text:
        return []

    matched = []
    for skill, pattern in _SKILL_PATTERNS.items():
        if pattern.search(text):
            matched.append(skill)

    return matched


def match_required_skills(
    extracted_skills: list[str],
    required_skills: list[str],
) -> dict:
    """
    Compare candidate skills against job requirements.

    Parameters
    ----------
    extracted_skills : list[str]
        Skills found in the candidate's resume.
    required_skills : list[str]
        Skills required for the job position.

    Returns
    -------
    dict
        {
            'matched_skills'    : list[str],  # skills present in both lists
            'missing_skills'    : list[str],  # required skills not in resume
            'matched_count'     : int,
            'required_count'    : int,
            'skill_match_pct'   : float       # 0.0 – 100.0
        }
    """
    if not required_skills:
        return {
            "matched_skills"  : [],
            "missing_skills"  : [],
            "matched_count"   : 0,
            "required_count"  : 0,
            "skill_match_pct" : 0.0,
        }

    # Normalise both lists for comparison
    extracted_normalised = {normalize_skill_text(s) for s in extracted_skills}
    required_normalised  = [normalize_skill_text(s) for s in required_skills]

    matched = []
    missing = []

    for req_norm, req_orig in zip(required_normalised, required_skills):
        if req_norm in extracted_normalised:
            matched.append(req_orig)
        else:
            missing.append(req_orig)

    total  = len(required_skills)
    pct    = (len(matched) / total * 100) if total > 0 else 0.0

    return {
        "matched_skills"  : matched,
        "missing_skills"  : missing,
        "matched_count"   : len(matched),
        "required_count"  : total,
        "skill_match_pct" : round(pct, 2),
    }


def get_skill_categories(skills: list[str]) -> dict[str, list[str]]:
    """
    Group a list of skill names into their predefined categories.

    Parameters
    ----------
    skills : list[str]
        Skill names to categorise.

    Returns
    -------
    dict[str, list[str]]
        Category → list of matching skills.
    """
    result: dict[str, list[str]] = {}
    skill_set = {normalize_skill_text(s) for s in skills}

    for category, category_skills in SKILL_CATEGORIES.items():
        matches = [s for s in category_skills if normalize_skill_text(s) in skill_set]
        if matches:
            result[category] = matches

    return result
