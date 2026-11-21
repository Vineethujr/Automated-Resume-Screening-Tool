"""
src/score_calculator.py
-----------------------
Calculates a final weighted score for each candidate based on:

  - Skill match percentage   (default weight: 50%)
  - JD similarity score      (default weight: 30%)
  - Experience score         (default weight: 10%)
  - Education score          (default weight: 10%)

All weights must sum to 1.0 (100%). Scores are clamped to [0, 100].

Design — "Not Assessed" vs "Zero"
----------------------------------
Experience and education scores are estimated from keyword signals in the
resume text.  There are two distinct outcomes:

  * Score detected  → a numeric value (0–100) with an explanation.
  * Not Assessed    → Python None; returned when no signals whatsoever
                      were found and assigning any number would be
                      invented / misleading.

When one or both optional components are Not Assessed, their weights are
excluded from the calculation and the remaining weights are proportionally
renormalised so that the final score always uses 100% of available evidence.

Example
-------
  skill=80  (weight 50%), similarity=90 (weight 30%),
  experience=Not Assessed, education=Not Assessed

  Available weight total = 0.50 + 0.30 = 0.80
  Normalised skill weight     = 0.50 / 0.80 = 0.625
  Normalised similarity weight = 0.30 / 0.80 = 0.375
  Final score = 80 × 0.625 + 90 × 0.375 = 83.75
"""

import re
from typing import Optional

# ---------------------------------------------------------------------------
# Sentinel – used internally to distinguish "not assessed" from zero
# ---------------------------------------------------------------------------
NOT_ASSESSED = None          # type alias for clarity in type hints

# ---------------------------------------------------------------------------
# Default scoring weights (must sum to 1.0)
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS: dict[str, float] = {
    "skill_weight"      : 0.50,
    "similarity_weight" : 0.30,
    "experience_weight" : 0.10,
    "education_weight"  : 0.10,
}

# ---------------------------------------------------------------------------
# Experience and education keyword signals
# ---------------------------------------------------------------------------

# Years patterns: "3 years", "2+ years", "5 year"
_YEARS_PATTERN = re.compile(r"(\d+)\s*\+?\s*year", re.IGNORECASE)

# Role-level keywords that signal actual work experience
_ROLE_KEYWORDS: list[str] = [
    "developer", "engineer", "analyst", "manager",
    "internship", "intern", "employment",
]

EDUCATION_KEYWORDS: dict[str, int] = {
    # keyword          → score (0-100)
    "phd"             : 100,
    "doctorate"       : 100,
    "master"          : 85,
    "msc"             : 85,
    "mba"             : 85,
    "m.tech"          : 85,
    "bachelor"        : 70,
    "bsc"             : 70,
    "b.tech"          : 70,
    "b.e"             : 70,
    "bca"             : 60,
    "diploma"         : 50,
    "associate"       : 50,
    "high school"     : 30,
    "12th"            : 30,
}


# ---------------------------------------------------------------------------
# Individual component scorers — return None when not assessable
# ---------------------------------------------------------------------------

def estimate_experience_score(text: str) -> tuple[Optional[float], str]:
    """
    Estimate an experience score from resume text.

    Returns
    -------
    tuple[float | None, str]
        (score_or_None, reason)

        score = None   →  "Not Assessed" — no experience signals found.
                          The weight for this component is excluded from
                          the final score calculation.

        score = float  →  Assessed value (0–100):
            0 years → 10   (fresher / no experience stated)
            1–2 yrs → 40   (junior)
            3–5 yrs → 70   (mid-level)
            6+ yrs  → 90   (senior)
            Role keywords present but no years → 20
    """
    if not text or not text.strip():
        return NOT_ASSESSED, "Not Assessed — no resume text available"

    text_lower = text.lower()

    # Priority 1: explicit year mentions
    year_matches = _YEARS_PATTERN.findall(text_lower)
    if year_matches:
        years = max(int(y) for y in year_matches)
        if years == 0:
            return 10.0, "0 years mentioned (fresher / student)"
        elif years <= 2:
            return 40.0, f"{years} year(s) of experience detected"
        elif years <= 5:
            return 70.0, f"{years} year(s) of experience detected"
        else:
            return 90.0, f"{years}+ year(s) of experience detected"

    # Priority 2: role-level keywords (developer, engineer, intern, …)
    found_roles = [kw for kw in _ROLE_KEYWORDS if kw in text_lower]
    if found_roles:
        return 20.0, (
            f"Role keywords found (no explicit years stated): "
            f"{', '.join(found_roles[:3])}"
        )

    # Priority 3: section header signals
    if "work experience" in text_lower or "employment history" in text_lower:
        return 20.0, "Work experience section detected (no years or roles stated)"

    # Nothing found — genuinely Not Assessed
    return NOT_ASSESSED, "Not Assessed — no experience information found in resume"


def estimate_education_score(text: str) -> tuple[Optional[float], str]:
    """
    Estimate an education score from resume text by detecting degree keywords.

    Returns
    -------
    tuple[float | None, str]
        (score_or_None, reason)

        score = None  →  "Not Assessed" — no degree keywords found.
        score = float →  Score for the highest detected qualification.
    """
    if not text or not text.strip():
        return NOT_ASSESSED, "Not Assessed — no resume text available"

    text_lower = text.lower()
    best_score  = -1
    best_reason = ""

    for keyword, score in EDUCATION_KEYWORDS.items():
        if keyword in text_lower and score > best_score:
            best_score  = score
            best_reason = f"Qualification detected: '{keyword}'"

    if best_score < 0:
        return NOT_ASSESSED, "Not Assessed — no education keywords found in resume"

    return float(best_score), best_reason


# ---------------------------------------------------------------------------
# Weight renormalisation
# ---------------------------------------------------------------------------

def _normalise_weights(
    weights: dict[str, float],
    exp_assessed: bool,
    edu_assessed: bool,
) -> tuple[dict[str, float], str]:
    """
    Return a copy of weights with any Not-Assessed components removed and
    the remaining weights renormalised to sum to 1.0.

    Parameters
    ----------
    weights        : original weight dict (four keys, sum = 1.0)
    exp_assessed   : True if experience produced a numeric score
    edu_assessed   : True if education produced a numeric score

    Returns
    -------
    tuple[dict, str]
        (adjusted_weights, score_basis_note)
        adjusted_weights has only the keys that are actually used.
        score_basis_note is a human-readable string for the report.
    """
    # Build the set of active components
    active = {
        "skill_weight"      : weights["skill_weight"],
        "similarity_weight" : weights["similarity_weight"],
    }
    if exp_assessed:
        active["experience_weight"] = weights["experience_weight"]
    if edu_assessed:
        active["education_weight"] = weights["education_weight"]

    total = sum(active.values())

    # Renormalise
    normalised = {k: round(v / total, 6) for k, v in active.items()}

    # Build a readable note
    components_used = []
    if "skill_weight" in normalised:
        components_used.append(f"Skills ({normalised['skill_weight']*100:.1f}%)")
    if "similarity_weight" in normalised:
        components_used.append(f"JD Similarity ({normalised['similarity_weight']*100:.1f}%)")
    if "experience_weight" in normalised:
        components_used.append(f"Experience ({normalised['experience_weight']*100:.1f}%)")
    if "education_weight" in normalised:
        components_used.append(f"Education ({normalised['education_weight']*100:.1f}%)")

    not_assessed = []
    if not exp_assessed:
        not_assessed.append("Experience")
    if not edu_assessed:
        not_assessed.append("Education")

    if not_assessed:
        note = (
            f"Score calculated from: {', '.join(components_used)}. "
            f"Not Assessed (excluded): {', '.join(not_assessed)}."
        )
    else:
        note = f"Score calculated from all components: {', '.join(components_used)}."

    return normalised, note


# ---------------------------------------------------------------------------
# Main scoring function
# ---------------------------------------------------------------------------

def calculate_final_score(
    skill_match_pct   : float,
    similarity_score  : float,
    resume_text       : str = "",
    weights           : dict | None = None,
) -> dict:
    """
    Compute a weighted final score for a candidate.

    When experience or education cannot be assessed (no detectable signals),
    their weights are excluded and the remaining weights are renormalised so
    the final score always reflects 100% of the assessable evidence.

    Parameters
    ----------
    skill_match_pct  : float   — % of required skills matched (0–100)
    similarity_score : float   — TF-IDF cosine similarity to JD (0–100)
    resume_text      : str     — raw resume text for exp/edu estimation
    weights          : dict    — custom weights; defaults to DEFAULT_WEIGHTS

    Returns
    -------
    dict with keys:
        'skill_score'       : float
        'similarity_score'  : float
        'experience_score'  : float | None   (None = Not Assessed)
        'education_score'   : float | None   (None = Not Assessed)
        'final_score'       : float          (0 – 100)
        'weights_used'      : dict           (renormalised active weights)
        'experience_reason' : str
        'education_reason'  : str
        'score_basis'       : str            (explains which components used)
    """
    # --- Validate / resolve weights ---
    if weights is None:
        weights = DEFAULT_WEIGHTS.copy()
    else:
        _validate_weights(weights)

    # --- Clamp always-available inputs ---
    skill_score      = float(min(max(skill_match_pct,  0.0), 100.0))
    similarity_score = float(min(max(similarity_score, 0.0), 100.0))

    # --- Estimate optional components ---
    experience_score, exp_reason = estimate_experience_score(resume_text)
    education_score,  edu_reason = estimate_education_score(resume_text)

    exp_assessed = experience_score is not NOT_ASSESSED
    edu_assessed = education_score  is not NOT_ASSESSED

    # --- Renormalise weights around available components ---
    active_weights, score_basis = _normalise_weights(weights, exp_assessed, edu_assessed)

    # --- Weighted sum (only assessed components) ---
    final_score = (
        skill_score * active_weights["skill_weight"] +
        similarity_score * active_weights["similarity_weight"]
    )
    if exp_assessed:
        final_score += experience_score * active_weights["experience_weight"]
    if edu_assessed:
        final_score += education_score  * active_weights["education_weight"]

    final_score = round(min(max(final_score, 0.0), 100.0), 2)

    return {
        "skill_score"       : round(skill_score, 2),
        "similarity_score"  : round(similarity_score, 2),
        "experience_score"  : round(experience_score, 2) if exp_assessed else NOT_ASSESSED,
        "education_score"   : round(education_score, 2)  if edu_assessed else NOT_ASSESSED,
        "final_score"       : final_score,
        "weights_used"      : active_weights,
        "experience_reason" : exp_reason,
        "education_reason"  : edu_reason,
        "score_basis"       : score_basis,
    }


# ---------------------------------------------------------------------------
# Weight validation
# ---------------------------------------------------------------------------

def _validate_weights(weights: dict) -> None:
    """
    Raise ValueError if the supplied weight dictionary is invalid.

    Rules
    -----
    * Must contain all four required keys.
    * All values must be between 0 and 1.
    * Values must sum to approximately 1.0 (tolerance ±0.01).
    """
    required_keys = {
        "skill_weight", "similarity_weight",
        "experience_weight", "education_weight",
    }

    missing = required_keys - weights.keys()
    if missing:
        raise ValueError(f"Missing weight keys: {missing}")

    for key, val in weights.items():
        if not (0.0 <= val <= 1.0):
            raise ValueError(f"Weight '{key}' = {val} is out of range [0, 1]")

    total = sum(weights[k] for k in required_keys)
    if abs(total - 1.0) > 0.01:
        raise ValueError(
            f"Weights must sum to 1.0, but they sum to {total:.4f}"
        )
