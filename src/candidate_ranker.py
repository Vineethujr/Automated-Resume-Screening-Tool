"""
src/candidate_ranker.py
-----------------------
Sorts, ranks, and generates shortlisting recommendations for candidates.

Thresholds (configurable)
--------------------------
  SHORTLIST_THRESHOLD  : Candidates scoring at or above this are
                         recommended for shortlisting.
  REVIEW_THRESHOLD     : Candidates scoring between REVIEW_THRESHOLD and
                         SHORTLIST_THRESHOLD are flagged for manual review.
  Below REVIEW_THRESHOLD → Not shortlisted (still subject to human review).

IMPORTANT
---------
This module produces RECOMMENDATIONS only.  It does not make final
hiring or rejection decisions.  Every recommendation must be reviewed
by a human recruiter.
"""

# ---------------------------------------------------------------------------
# Configurable thresholds
# ---------------------------------------------------------------------------

SHORTLIST_THRESHOLD: float = 60.0   # score >= this → "Shortlisted"
REVIEW_THRESHOLD:    float = 40.0   # score >= this → "Manual Review"
# score < REVIEW_THRESHOLD          → "Not Shortlisted"


# ---------------------------------------------------------------------------
# Recommendation logic
# ---------------------------------------------------------------------------

def get_recommendation(
    final_score: float,
    shortlist_threshold: float = SHORTLIST_THRESHOLD,
    review_threshold:    float = REVIEW_THRESHOLD,
) -> str:
    """
    Return a transparent screening recommendation based on the candidate's
    final score.

    Parameters
    ----------
    final_score : float
        Candidate's weighted final score (0–100).
    shortlist_threshold : float
        Minimum score to be recommended for shortlisting.
    review_threshold : float
        Minimum score to be flagged for manual review.

    Returns
    -------
    str
        One of: "Shortlisted", "Manual Review", "Not Shortlisted".
    """
    if final_score >= shortlist_threshold:
        return "Shortlisted"
    elif final_score >= review_threshold:
        return "Manual Review"
    else:
        return "Not Shortlisted"


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def rank_candidates(
    candidates: list[dict],
    shortlist_threshold: float = SHORTLIST_THRESHOLD,
    review_threshold:    float = REVIEW_THRESHOLD,
) -> list[dict]:
    """
    Sort candidates by final score (highest first), assign ranks, and
    attach screening recommendations.

    Tie-breaking
    ------------
    Candidates with equal final scores are sub-sorted alphabetically by
    name to produce a deterministic, fair ordering.

    Parameters
    ----------
    candidates : list[dict]
        Each dict must contain at least:
            'final_score' : float
            'name'        : str   (used for tie-breaking)
        Additional keys are passed through unchanged.
    shortlist_threshold : float
    review_threshold    : float

    Returns
    -------
    list[dict]
        Ranked list; each dict gains:
            'rank'           : int   (1 = best)
            'recommendation' : str
    """
    if not candidates:
        return []

    # Sort: primary = final_score descending, secondary = name ascending
    sorted_candidates = sorted(
        candidates,
        key=lambda c: (-c.get("final_score", 0.0), c.get("name", "").lower()),
    )

    ranked = []
    for rank, candidate in enumerate(sorted_candidates, start=1):
        updated = candidate.copy()
        updated["rank"] = rank
        updated["recommendation"] = get_recommendation(
            candidate.get("final_score", 0.0),
            shortlist_threshold,
            review_threshold,
        )
        ranked.append(updated)

    return ranked


# ---------------------------------------------------------------------------
# Summary helpers
# ---------------------------------------------------------------------------

def get_shortlisted(ranked_candidates: list[dict]) -> list[dict]:
    """Return only candidates recommended for shortlisting."""
    return [c for c in ranked_candidates if c.get("recommendation") == "Shortlisted"]


def get_manual_review(ranked_candidates: list[dict]) -> list[dict]:
    """Return candidates flagged for manual review."""
    return [c for c in ranked_candidates if c.get("recommendation") == "Manual Review"]


def get_not_shortlisted(ranked_candidates: list[dict]) -> list[dict]:
    """Return candidates not shortlisted."""
    return [c for c in ranked_candidates if c.get("recommendation") == "Not Shortlisted"]


def build_ranking_summary(ranked_candidates: list[dict]) -> dict:
    """
    Produce a high-level summary of the screening results.

    Parameters
    ----------
    ranked_candidates : list[dict]
        Output of rank_candidates().

    Returns
    -------
    dict
        {
            'total'          : int,
            'shortlisted'    : int,
            'manual_review'  : int,
            'not_shortlisted': int,
            'top_candidate'  : str | None,
            'average_score'  : float,
        }
    """
    if not ranked_candidates:
        return {
            "total"           : 0,
            "shortlisted"     : 0,
            "manual_review"   : 0,
            "not_shortlisted" : 0,
            "top_candidate"   : None,
            "average_score"   : 0.0,
        }

    scores = [c.get("final_score", 0.0) for c in ranked_candidates]
    average_score = round(sum(scores) / len(scores), 2)

    return {
        "total"           : len(ranked_candidates),
        "shortlisted"     : len(get_shortlisted(ranked_candidates)),
        "manual_review"   : len(get_manual_review(ranked_candidates)),
        "not_shortlisted" : len(get_not_shortlisted(ranked_candidates)),
        "top_candidate"   : ranked_candidates[0].get("name", "Unknown"),
        "average_score"   : average_score,
    }
