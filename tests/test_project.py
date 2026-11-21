"""
tests/test_project.py
---------------------
Unified automated test suite for the Automated Resume Screening Tool.

Covers:
  - All 8 source module imports
  - TXT, DOCX, and PDF text extraction
  - Unsupported file format handling
  - Empty folder / non-existent folder resilience
  - Text cleaning and normalisation
  - Skill extraction including C/C++ boundary edge cases
  - Skill matching and missing-skill detection
  - TF-IDF cosine similarity (high, low, empty inputs)
  - Score calculator — full components and Not Assessed logic
  - Weight renormalisation when components are missing
  - Candidate ranking and recommendation thresholds
  - Input validation
  - Resilience when one resume file is empty
  - CSV report and summary report generation
  - Full end-to-end pipeline with real sample resumes
  - app.py syntax validation

Run with:
    python -m unittest discover -s tests -v

Or run directly:
    python tests/test_project.py
"""

import ast
import csv
import os
import sys
import unittest

# Ensure the project root is on sys.path so src/ imports work correctly.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# ---------------------------------------------------------------------------
# Lazy imports — imported inside each test so a single module failure does
# not prevent other tests from running.
# ---------------------------------------------------------------------------

def _import_all():
    """Import every public symbol used across the test suite and return them."""
    from src.resume_parser    import extract_text, parse_resume, load_resumes_from_folder
    from src.text_cleaner     import clean_text, normalize_skill_text
    from src.skill_extractor  import extract_skills, match_required_skills
    from src.similarity       import calculate_similarity, calculate_batch_similarity
    from src.score_calculator import (
        calculate_final_score,
        estimate_experience_score,
        estimate_education_score,
        _normalise_weights,
        DEFAULT_WEIGHTS,
    )
    from src.candidate_ranker import rank_candidates, build_ranking_summary, get_recommendation
    from src.report_generator import generate_csv_report, generate_summary_report, _fmt_score
    from src.screening_engine import screen_resumes_from_folder, validate_inputs
    return {
        "extract_text"              : extract_text,
        "parse_resume"              : parse_resume,
        "load_resumes_from_folder"  : load_resumes_from_folder,
        "clean_text"                : clean_text,
        "normalize_skill_text"      : normalize_skill_text,
        "extract_skills"            : extract_skills,
        "match_required_skills"     : match_required_skills,
        "calculate_similarity"      : calculate_similarity,
        "calculate_batch_similarity": calculate_batch_similarity,
        "calculate_final_score"     : calculate_final_score,
        "estimate_experience_score" : estimate_experience_score,
        "estimate_education_score"  : estimate_education_score,
        "_normalise_weights"        : _normalise_weights,
        "DEFAULT_WEIGHTS"           : DEFAULT_WEIGHTS,
        "rank_candidates"           : rank_candidates,
        "build_ranking_summary"     : build_ranking_summary,
        "get_recommendation"        : get_recommendation,
        "generate_csv_report"       : generate_csv_report,
        "generate_summary_report"   : generate_summary_report,
        "_fmt_score"                : _fmt_score,
        "screen_resumes_from_folder": screen_resumes_from_folder,
        "validate_inputs"           : validate_inputs,
    }


# ---------------------------------------------------------------------------
# Helper — standard resume folder path relative to project root
# ---------------------------------------------------------------------------
RESUMES_DIR = os.path.join(PROJECT_ROOT, "resumes")
OUTPUTS_DIR = os.path.join(PROJECT_ROOT, "outputs")

# ---------------------------------------------------------------------------
# Test classes
# ---------------------------------------------------------------------------

class TestModuleImports(unittest.TestCase):
    """T01 — All 8 source modules import without errors."""

    def test_all_imports(self):
        try:
            symbols = _import_all()
            self.assertGreater(len(symbols), 0)
        except Exception as exc:
            self.fail(f"Module import failed: {exc}")


class TestTextExtraction(unittest.TestCase):
    """T02–T05 — Resume text extraction for supported and unsupported formats."""

    def setUp(self):
        self.s = _import_all()

    def test_txt_extraction(self):
        path = os.path.join(RESUMES_DIR, "alice_johnson.txt")
        text = self.s["extract_text"](path)
        self.assertGreater(len(text), 100, "TXT text too short")
        self.assertIn("Alice Johnson", text)
        self.assertIn("alice.johnson@email.com", text)

    def test_docx_extraction(self):
        path = os.path.join(RESUMES_DIR, "frank_rivera.docx")
        text = self.s["extract_text"](path)
        self.assertGreater(len(text), 100, "DOCX text too short")
        self.assertIn("Python", text)

    def test_pdf_extraction(self):
        path = os.path.join(RESUMES_DIR, "sample_candidate.pdf")
        if not os.path.isfile(path):
            self.skipTest("sample_candidate.pdf not present — skipping PDF test")
        text = self.s["extract_text"](path)
        self.assertGreater(len(text), 50, "PDF text too short")

    def test_unsupported_format_returns_empty_string(self):
        tmp = os.path.join(RESUMES_DIR, "_test_unsupported_fmt.xyz")
        with open(tmp, "w") as f:
            f.write("test content")
        try:
            result = self.s["extract_text"](tmp)
            self.assertEqual(result, "", f"Expected empty string, got: {result!r}")
        finally:
            if os.path.exists(tmp):
                os.remove(tmp)


class TestFolderHandling(unittest.TestCase):
    """T06–T07 — load_resumes_from_folder with edge-case folders."""

    def setUp(self):
        self.s = _import_all()

    def test_empty_folder_returns_empty_list(self):
        empty = os.path.join(RESUMES_DIR, "_empty_test_dir")
        os.makedirs(empty, exist_ok=True)
        try:
            result = self.s["load_resumes_from_folder"](empty)
            self.assertEqual(result, [])
        finally:
            os.rmdir(empty)

    def test_nonexistent_folder_returns_empty_list(self):
        result = self.s["load_resumes_from_folder"](
            os.path.join(RESUMES_DIR, "_nonexistent_xyz_folder_12345")
        )
        self.assertEqual(result, [])


class TestTextCleaning(unittest.TestCase):
    """T08 — Text cleaning and normalisation."""

    def setUp(self):
        self.clean_text = _import_all()["clean_text"]

    def test_cleaning_removes_email_and_normalises(self):
        dirty = "Hello World!   Email: test@test.com   Phone: 555-1234   C++ and Python!"
        cleaned = self.clean_text(dirty)
        self.assertNotIn("test@test.com", cleaned, "Email not removed")
        self.assertIn("c++", cleaned,               "C++ not preserved")
        self.assertIn("python", cleaned,            "python not found")
        self.assertEqual(cleaned, cleaned.lower(),  "Text not fully lowercased")


class TestSkillExtraction(unittest.TestCase):
    """T09–T10 — Skill detection and matching."""

    def setUp(self):
        self.s = _import_all()

    def test_skill_extraction_and_c_boundary(self):
        text   = "Expert in Python, Machine Learning, Pandas, SQL, NLP and Communication"
        skills = self.s["extract_skills"](text)
        self.assertIn("Python",           skills)
        self.assertIn("Machine Learning", skills)
        self.assertIn("Communication",    skills)
        # 'C' must NOT falsely match inside 'Communication'
        text2  = "Communication is a soft skill"
        skills2 = self.s["extract_skills"](text2)
        self.assertNotIn("C", skills2, f"C falsely matched in: {skills2}")

    def test_skill_matching_and_missing(self):
        extracted = ["Python", "Machine Learning", "Pandas"]
        required  = ["Python", "Machine Learning", "Java", "Deep Learning"]
        result = self.s["match_required_skills"](extracted, required)
        self.assertEqual(result["matched_skills"], ["Python", "Machine Learning"])
        self.assertEqual(set(result["missing_skills"]), {"Java", "Deep Learning"})
        self.assertEqual(result["skill_match_pct"], 50.0)


class TestSimilarity(unittest.TestCase):
    """T11 — TF-IDF cosine similarity."""

    def setUp(self):
        self.calc = _import_all()["calculate_similarity"]

    def test_high_similarity(self):
        s = self.calc(
            "Python developer machine learning scikit-learn pandas data science",
            "Python machine learning data science pandas scikit"
        )
        self.assertGreater(s, 20, f"High-match score too low: {s}")
        self.assertLessEqual(s, 100)

    def test_empty_resume_returns_zero(self):
        s = self.calc("", "some job description")
        self.assertEqual(s, 0.0)

    def test_low_similarity_less_than_high(self):
        s_high = self.calc(
            "Python machine learning data science pandas",
            "Python machine learning data science pandas"
        )
        s_low = self.calc(
            "marketing sales campaigns social media branding",
            "Python machine learning data science"
        )
        self.assertLess(s_low, s_high)


class TestScoreCalculator(unittest.TestCase):
    """T12–T14 — Scoring engine including Not Assessed logic."""

    def setUp(self):
        self.s = _import_all()

    def test_all_components_assessed(self):
        """Explicit year + degree keywords → all four components assessed."""
        result = self.s["calculate_final_score"](
            80.0, 65.0,
            "Python developer 4 years experience bachelor of science computer science"
        )
        self.assertEqual(result["experience_score"], 70.0,
                         f"Exp wrong: {result['experience_score']}")
        self.assertEqual(result["education_score"],  70.0,
                         f"Edu wrong: {result['education_score']}")
        expected = round(80.0*0.50 + 65.0*0.30 + 70.0*0.10 + 70.0*0.10, 2)
        self.assertAlmostEqual(result["final_score"], expected, places=1)
        self.assertNotIn("Not Assessed", result.get("score_basis", ""))

    def test_both_missing_returns_none_and_renormalises(self):
        """No signals → both return None; weights renormalised over skill + JD."""
        result = self.s["calculate_final_score"](
            50.0, 40.0,
            "some text with no recognisable experience or degree keywords"
        )
        self.assertIsNone(result["experience_score"],
                          f"Expected None, got {result['experience_score']}")
        self.assertIsNone(result["education_score"],
                          f"Expected None, got {result['education_score']}")
        self.assertIn("Not Assessed", result.get("experience_reason", ""))
        self.assertIn("Not Assessed", result.get("education_reason",  ""))
        # Renormalised: skill=50/80, jd=30/80
        expected = round(50.0 * (50/80) + 40.0 * (30/80), 2)
        self.assertAlmostEqual(result["final_score"], expected, places=1)
        self.assertIn("Not Assessed", result.get("score_basis", ""))

    def test_experience_missing_only(self):
        """Education detected; experience not → 3-component renormalisation."""
        result = self.s["calculate_final_score"](
            70.0, 60.0,
            "bachelor of science computer science graduate"
        )
        self.assertIsNone(result["experience_score"])
        self.assertEqual(result["education_score"], 70.0)
        # skill=50/90, jd=30/90, edu=10/90
        expected = round(70.0*(50/90) + 60.0*(30/90) + 70.0*(10/90), 2)
        self.assertAlmostEqual(result["final_score"], expected, places=1)

    def test_education_missing_only(self):
        """Experience detected; education not → 3-component renormalisation."""
        result = self.s["calculate_final_score"](
            60.0, 50.0,
            "software engineer 2 years of experience developing apis"
        )
        self.assertIsNone(result["education_score"])
        self.assertEqual(result["experience_score"], 40.0)
        # skill=50/90, jd=30/90, exp=10/90
        expected = round(60.0*(50/90) + 50.0*(30/90) + 40.0*(10/90), 2)
        self.assertAlmostEqual(result["final_score"], expected, places=1)


class TestExperienceEducationEstimators(unittest.TestCase):
    """T15–T18 — Unit tests for individual estimator functions."""

    def setUp(self):
        self.exp = _import_all()["estimate_experience_score"]
        self.edu = _import_all()["estimate_education_score"]

    def test_experience_no_signals_returns_none(self):
        score, reason = self.exp("some irrelevant text with no experience signals")
        self.assertIsNone(score)
        self.assertIn("Not Assessed", reason)

    def test_experience_with_years_returns_score(self):
        score, reason = self.exp("Python developer 4 years of experience in machine learning")
        self.assertEqual(score, 70.0, f"Got {score}")
        self.assertIn("year", reason.lower())

    def test_education_no_signals_returns_none(self):
        score, reason = self.edu("some irrelevant text with no degree keywords")
        self.assertIsNone(score)
        self.assertIn("Not Assessed", reason)

    def test_education_with_degree_returns_score(self):
        score, reason = self.edu("Bachelor of Science in Computer Science from State University")
        self.assertEqual(score, 70.0, f"Got {score}")
        self.assertIn("Qualification", reason)


class TestWeightNormalisation(unittest.TestCase):
    """T19 — _normalise_weights proportional redistribution."""

    def setUp(self):
        self.s = _import_all()

    def test_both_missing_renormalises_to_two_weights(self):
        w = self.s["DEFAULT_WEIGHTS"].copy()
        adj, _ = self.s["_normalise_weights"](w, exp_assessed=False, edu_assessed=False)
        self.assertEqual(set(adj.keys()), {"skill_weight", "similarity_weight"})
        self.assertAlmostEqual(adj["skill_weight"],      0.625, places=3)
        self.assertAlmostEqual(adj["similarity_weight"], 0.375, places=3)
        self.assertAlmostEqual(sum(adj.values()),        1.0,   places=3)

    def test_all_present_keeps_four_weights_summing_to_one(self):
        w = self.s["DEFAULT_WEIGHTS"].copy()
        adj, _ = self.s["_normalise_weights"](w, exp_assessed=True, edu_assessed=True)
        self.assertEqual(len(adj), 4)
        self.assertAlmostEqual(sum(adj.values()), 1.0, places=3)


class TestFmtScore(unittest.TestCase):
    """T20 — _fmt_score helper in report_generator."""

    def setUp(self):
        self.fmt = _import_all()["_fmt_score"]

    def test_none_returns_not_assessed(self):
        self.assertEqual(self.fmt(None), "Not Assessed")

    def test_numeric_returns_string(self):
        self.assertEqual(self.fmt(70.0), "70.0")

    def test_zero_returns_zero_string(self):
        self.assertEqual(self.fmt(0.0), "0.0")


class TestRankingAndRecommendations(unittest.TestCase):
    """T21 — Candidate ranking and recommendation thresholds."""

    def setUp(self):
        self.rank = _import_all()["rank_candidates"]

    def test_ranking_order_and_recommendations(self):
        candidates = [
            {"name": "Alice", "final_score": 75.0},
            {"name": "Bob",   "final_score": 45.0},
            {"name": "Carol", "final_score": 30.0},
            {"name": "Dave",  "final_score": 60.0},
        ]
        ranked = self.rank(candidates)
        self.assertEqual(ranked[0]["name"], "Alice")
        self.assertEqual(ranked[0]["rank"], 1)
        self.assertEqual(ranked[0]["recommendation"], "Shortlisted")   # 75
        self.assertEqual(ranked[1]["recommendation"], "Shortlisted")   # Dave 60
        self.assertEqual(ranked[2]["recommendation"], "Manual Review") # Bob 45
        self.assertEqual(ranked[3]["recommendation"], "Not Shortlisted") # Carol 30


class TestInputValidation(unittest.TestCase):
    """T22 — validate_inputs error messages."""

    def setUp(self):
        self.validate = _import_all()["validate_inputs"]

    def test_missing_jd(self):
        errors = self.validate("", ["Python"])
        self.assertTrue(any("Job description" in e for e in errors))

    def test_missing_skills(self):
        errors = self.validate("Some JD text", [])
        self.assertTrue(any("skills" in e.lower() for e in errors))

    def test_valid_inputs_returns_no_errors(self):
        errors = self.validate("Some JD text", ["Python"])
        self.assertEqual(errors, [])


class TestResilienceEmptyFile(unittest.TestCase):
    """T23 — An empty resume file is skipped; valid resumes are still processed."""

    def setUp(self):
        self.screen = _import_all()["screen_resumes_from_folder"]

    def test_empty_file_skipped_others_processed(self):
        empty_path = os.path.join(RESUMES_DIR, "_empty_resume_test.txt")
        with open(empty_path, "w") as f:
            f.write("")
        try:
            jd     = "Python developer machine learning data science pandas scikit-learn sql"
            skills = ["Python", "Machine Learning", "Pandas", "SQL"]
            ranked, summary = self.screen(RESUMES_DIR, jd, skills)
            self.assertGreaterEqual(summary["total"], 2,
                                    f"Expected >=2 processed, got {summary['total']}")
        finally:
            if os.path.exists(empty_path):
                os.remove(empty_path)


class TestCSVReportGeneration(unittest.TestCase):
    """T24–T27 — CSV report writing, headers, and Not Assessed values."""

    def setUp(self):
        self.s = _import_all()

    def _run_pipeline(self):
        jd     = "Python developer machine learning data science pandas scikit-learn sql"
        skills = ["Python", "Machine Learning", "Pandas", "SQL"]
        ranked, summary = self.s["screen_resumes_from_folder"](RESUMES_DIR, jd, skills)
        return ranked, summary

    def test_screening_report_created_with_data_rows(self):
        ranked, _ = self._run_pipeline()
        path = self.s["generate_csv_report"](ranked)
        self.assertTrue(os.path.isfile(path), "Screening report file not created")
        with open(path, encoding="utf-8") as f:
            lines = f.readlines()
        self.assertGreater(len(lines), 1, "CSV has no data rows")
        header = lines[0].strip()
        self.assertIn("Rank",           header)
        self.assertIn("Final Score (%)", header)
        self.assertIn("Recommendation", header)
        self.assertIn("Score Basis",    header)

    def test_summary_report_created(self):
        _, summary = self._run_pipeline()
        path = self.s["generate_summary_report"](summary)
        self.assertTrue(os.path.isfile(path), "Summary report not created")

    def test_not_assessed_written_to_csv(self):
        """A candidate with None experience/education scores appears as 'Not Assessed' in CSV."""
        candidate = {
            "rank"             : 1,
            "name"             : "Test Candidate",
            "email"            : "test@example.com",
            "phone"            : "555-0000",
            "filename"         : "test.txt",
            "extracted_skills" : ["Python"],
            "matched_skills"   : ["Python"],
            "missing_skills"   : ["SQL"],
            "skill_score"      : 50.0,
            "similarity_score" : 40.0,
            "experience_score" : None,
            "education_score"  : None,
            "final_score"      : 68.75,
            "recommendation"   : "Shortlisted",
            "score_basis"      : (
                "Score calculated from: Skills, JD Similarity. "
                "Not Assessed (excluded): Experience, Education."
            ),
            "experience_reason": "Not Assessed — no experience information found",
            "education_reason" : "Not Assessed — no education keywords found",
        }
        fname = "test_not_assessed_unified.csv"
        path  = os.path.join(OUTPUTS_DIR, fname)
        try:
            self.s["generate_csv_report"]([candidate], filename=fname)
            with open(path, encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            row = rows[0]
            self.assertEqual(row["Experience Score (%)"], "Not Assessed")
            self.assertEqual(row["Education Score (%)"],  "Not Assessed")
            self.assertIn("Not Assessed", row.get("Score Basis", ""))
            self.assertNotEqual(row["Final Score (%)"], "")
        finally:
            if os.path.exists(path):
                os.remove(path)


class TestFullPipeline(unittest.TestCase):
    """T28–T30 — End-to-end pipeline with real sample resumes."""

    def setUp(self):
        self.screen = _import_all()["screen_resumes_from_folder"]
        self.jd = (
            "We are looking for a Data Scientist with expertise in Python, "
            "machine learning, NLP, Pandas, NumPy, Scikit-learn, SQL and "
            "strong communication skills."
        )
        self.skills = [
            "Python", "Machine Learning", "Pandas", "NumPy",
            "Scikit-learn", "SQL", "NLP", "Communication", "Problem Solving",
        ]

    def test_pipeline_produces_valid_ranked_candidates(self):
        ranked, summary = self.screen(RESUMES_DIR, self.jd, self.skills)
        self.assertGreater(summary["total"], 0, "No candidates processed")
        # Scores are sorted descending
        scores = [c["final_score"] for c in ranked]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_every_candidate_has_numeric_final_score(self):
        ranked, _ = self.screen(RESUMES_DIR, self.jd, self.skills)
        for c in ranked:
            self.assertIsInstance(c["final_score"], (int, float),
                                  f"{c.get('name')}: final_score is not numeric")

    def test_not_assessed_candidates_have_score_basis(self):
        ranked, _ = self.screen(RESUMES_DIR, self.jd, self.skills)
        for c in ranked:
            exp = c.get("experience_score")
            edu = c.get("education_score")
            if exp is None or edu is None:
                self.assertIn("Not Assessed", c.get("score_basis", ""),
                              f"{c.get('name')}: missing Not Assessed in score_basis")


class TestAppSyntax(unittest.TestCase):
    """T31 — app.py parses without syntax errors."""

    def test_app_py_syntax(self):
        path = os.path.join(PROJECT_ROOT, "app.py")
        self.assertTrue(os.path.isfile(path), "app.py not found")
        with open(path, encoding="utf-8") as f:
            source = f.read()
        try:
            ast.parse(source)
        except SyntaxError as exc:
            self.fail(f"app.py has a syntax error: {exc}")


# ---------------------------------------------------------------------------
# Entry point — also runnable directly with:  python tests/test_project.py
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    unittest.main(verbosity=2)
