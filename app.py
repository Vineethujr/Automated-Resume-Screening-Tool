"""
app.py
------
Streamlit interactive dashboard for the Automated Resume Screening Tool.

Run with:
    streamlit run app.py

Dashboard sections
------------------
  1. Project header and description.
  2. Job requirements (title, description, required skills).
  3. Resume upload (PDF, DOCX, TXT).
  4. Screening results (scores, rankings, skills).
  5. Shortlisting recommendations.
  6. CSV download.
"""

import os
import sys
import io
import csv

import streamlit as st
import pandas as pd

# Ensure src/ modules are importable
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, PROJECT_ROOT)

from src.screening_engine import screen_resumes_from_uploads, validate_inputs
from src.candidate_ranker import (
    get_shortlisted, get_manual_review, get_not_shortlisted,
)


# ---------------------------------------------------------------------------
# Page configuration (must be the very first Streamlit call)
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title = "Automated Resume Screening Tool",
    page_icon  = "📄",
    layout     = "wide",
    initial_sidebar_state = "expanded",
)


# ---------------------------------------------------------------------------
# Custom CSS for a cleaner look
# ---------------------------------------------------------------------------

st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1f4e79;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.0rem;
        color: #555555;
        margin-bottom: 1.5rem;
    }
    .section-header {
        font-size: 1.3rem;
        font-weight: 600;
        color: #1f4e79;
        border-bottom: 2px solid #1f4e79;
        padding-bottom: 4px;
        margin-top: 1.5rem;
        margin-bottom: 1rem;
    }
    .recommendation-shortlisted {
        color: #1a7a1a;
        font-weight: 700;
    }
    .recommendation-review {
        color: #c47a00;
        font-weight: 700;
    }
    .recommendation-not {
        color: #c0392b;
        font-weight: 700;
    }
    .disclaimer-box {
        background-color: #fff8e1;
        border-left: 4px solid #f0ad00;
        padding: 0.8rem 1rem;
        border-radius: 4px;
        font-size: 0.88rem;
        color: #5a4a00;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Section 1: Header
# ---------------------------------------------------------------------------

st.markdown('<p class="main-header">📄 Automated Resume Screening Tool</p>', unsafe_allow_html=True)
st.markdown(
    '<p class="sub-header">An educational ATS-style simulation — '
    'screen, score, and rank candidates against a job description using '
    'TF-IDF and cosine similarity.</p>',
    unsafe_allow_html=True,
)

st.markdown(
    '<div class="disclaimer-box">'
    '⚠️ <strong>Educational Simulation:</strong> This tool is intended for learning purposes '
    'and uses synthetic data only. All screening recommendations are for guidance and '
    '<strong>must be reviewed by a human recruiter</strong> before any hiring decisions are made.'
    '</div>',
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Sidebar — Scoring configuration
# ---------------------------------------------------------------------------

with st.sidebar:
    st.header("⚙️ Scoring Configuration")
    st.caption("Adjust the weights for each scoring component. They must add up to 100%.")

    skill_w  = st.slider("Skill Match Weight (%)",      min_value=0, max_value=100, value=50, step=5)
    sim_w    = st.slider("JD Similarity Weight (%)",    min_value=0, max_value=100, value=30, step=5)
    exp_w    = st.slider("Experience Weight (%)",       min_value=0, max_value=100, value=10, step=5)
    edu_w    = st.slider("Education Weight (%)",        min_value=0, max_value=100, value=10, step=5)

    total_w  = skill_w + sim_w + exp_w + edu_w
    if total_w != 100:
        st.error(f"⚠️ Weights sum to {total_w}% — must equal 100%.")
        weights_valid = False
    else:
        st.success("✅ Weights sum to 100%")
        weights_valid = True

    custom_weights = {
        "skill_weight"      : skill_w  / 100,
        "similarity_weight" : sim_w    / 100,
        "experience_weight" : exp_w    / 100,
        "education_weight"  : edu_w    / 100,
    }

    st.markdown("---")
    st.header("📊 Shortlisting Thresholds")
    shortlist_threshold = st.slider(
        "Shortlist Threshold (%)", min_value=10, max_value=90, value=60, step=5,
        help="Candidates scoring at or above this are recommended for shortlisting.",
    )
    review_threshold = st.slider(
        "Manual Review Threshold (%)", min_value=10, max_value=90, value=40, step=5,
        help="Candidates scoring between this and the shortlist threshold are flagged for manual review.",
    )
    if review_threshold >= shortlist_threshold:
        st.warning("⚠️ Manual Review threshold must be below Shortlist threshold.")

    st.markdown("---")
    st.caption("Automated Resume Screening Tool — Educational Project")


# ---------------------------------------------------------------------------
# Section 2: Job Requirements
# ---------------------------------------------------------------------------

st.markdown('<p class="section-header">📋 Section 1: Job Requirements</p>', unsafe_allow_html=True)

col1, col2 = st.columns([1, 1])

with col1:
    job_title = st.text_input(
        "Job Title",
        placeholder="e.g. Data Scientist, Python Developer",
        help="Enter the title of the position you are hiring for.",
    )

    job_description = st.text_area(
        "Job Description",
        height=200,
        placeholder=(
            "Paste the full job description here.\n\n"
            "Example: We are looking for a Data Scientist with experience in "
            "Python, machine learning, and SQL..."
        ),
        help="The tool will compare each resume against this description using TF-IDF.",
    )

with col2:
    required_skills_input = st.text_area(
        "Required Skills (one per line or comma-separated)",
        height=200,
        placeholder=(
            "Python\nMachine Learning\nPandas\nNumPy\nScikit-learn\nSQL\nNLP\n"
            "Communication\nProblem Solving"
        ),
        help="List the skills required for the position. Each skill is matched against the resume.",
    )

    # Parse required skills from input
    if required_skills_input.strip():
        if "\n" in required_skills_input:
            required_skills = [s.strip() for s in required_skills_input.split("\n") if s.strip()]
        else:
            required_skills = [s.strip() for s in required_skills_input.split(",") if s.strip()]
    else:
        required_skills = []

    if required_skills:
        st.caption(f"✅ {len(required_skills)} required skill(s) entered.")
        with st.expander("View entered skills"):
            st.write(", ".join(required_skills))


# ---------------------------------------------------------------------------
# Section 3: Resume Upload
# ---------------------------------------------------------------------------

st.markdown('<p class="section-header">📁 Section 2: Resume Upload</p>', unsafe_allow_html=True)

uploaded_files = st.file_uploader(
    "Upload Resumes (PDF, DOCX, or TXT)",
    type=["pdf", "docx", "txt"],
    accept_multiple_files=True,
    help="Upload one or more resume files. All formats (PDF, DOCX, TXT) are supported.",
)

if uploaded_files:
    st.success(f"✅ {len(uploaded_files)} file(s) uploaded: {', '.join(f.name for f in uploaded_files)}")


# ---------------------------------------------------------------------------
# Section 4: Run Screening
# ---------------------------------------------------------------------------

st.markdown("---")

run_screening = st.button(
    "🚀 Run Screening",
    type="primary",
    disabled=(not weights_valid or review_threshold >= shortlist_threshold),
    help="Click to start resume screening.",
)

if run_screening:

    # Input validation
    errors = validate_inputs(job_description, required_skills)
    if not uploaded_files:
        errors.append("No resume files uploaded. Please upload at least one resume.")

    if errors:
        for err in errors:
            st.error(f"❌ {err}")
        st.stop()

    # Run the pipeline
    with st.spinner("🔍 Processing resumes... please wait."):
        ranked_candidates, summary = screen_resumes_from_uploads(
            uploaded_files      = uploaded_files,
            job_description     = job_description,
            required_skills     = required_skills,
            weights             = custom_weights,
            shortlist_threshold = shortlist_threshold,
            review_threshold    = review_threshold,
        )

    if not ranked_candidates:
        st.error("❌ No candidates could be processed. Check that your resume files contain extractable text.")
        st.stop()

    # Save results to session state
    st.session_state["ranked_candidates"] = ranked_candidates
    st.session_state["summary"]           = summary
    st.session_state["job_title"]         = job_title


# ---------------------------------------------------------------------------
# Section 5: Results (shown only after screening)
# ---------------------------------------------------------------------------

if "ranked_candidates" in st.session_state:

    ranked_candidates = st.session_state["ranked_candidates"]
    summary           = st.session_state["summary"]
    screened_title    = st.session_state.get("job_title", "Position")

    st.markdown(f'<p class="section-header">📊 Section 3: Screening Results — {screened_title}</p>',
                unsafe_allow_html=True)

    # --- Summary metrics ---
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Total Candidates",  summary.get("total", 0))
    col2.metric("✅ Shortlisted",    summary.get("shortlisted", 0))
    col3.metric("🔍 Manual Review",  summary.get("manual_review", 0))
    col4.metric("❌ Not Shortlisted", summary.get("not_shortlisted", 0))
    col5.metric("📈 Avg Score",      f"{summary.get('average_score', 0):.1f}%")

    # --- Ranking table ---
    st.markdown("#### 🏆 Candidate Ranking")

    def _fmt(val):
        """Format a score value: float → '72.5', None → 'N/A'."""
        return "N/A" if val is None else f"{val:.1f}"

    table_data = []
    for c in ranked_candidates:
        rec = c.get("recommendation", "N/A")
        rec_display = f"✅ {rec}" if rec == "Shortlisted" else \
                      f"🔍 {rec}" if rec == "Manual Review" else \
                      f"❌ {rec}"
        table_data.append({
            "Rank"            : c.get("rank"),
            "Name"            : c.get("name", "Unknown"),
            "File"            : c.get("filename", ""),
            "Skill Score %"   : _fmt(c.get("skill_score")),
            "JD Similarity %"  : _fmt(c.get("similarity_score")),
            "Experience %"    : _fmt(c.get("experience_score")),
            "Education %"     : _fmt(c.get("education_score")),
            "Final Score %"   : _fmt(c.get("final_score")),
            "Recommendation"  : rec_display,
        })

    df_table = pd.DataFrame(table_data)
    st.dataframe(df_table, use_container_width=True, hide_index=True)

    # --- Individual candidate cards ---
    st.markdown("#### 👤 Candidate Details")

    for c in ranked_candidates:
        rec   = c.get("recommendation", "N/A")
        score = c.get("final_score", 0)
        icon  = "✅" if rec == "Shortlisted" else "🔍" if rec == "Manual Review" else "❌"
        label = f"{icon} Rank #{c.get('rank')} — {c.get('name', 'Unknown')} | Score: {score:.1f}%"

        with st.expander(label):
            d1, d2, d3 = st.columns(3)

            with d1:
                st.markdown("**Contact**")
                st.write(f"📧 {c.get('email', 'Not found')}")
                st.write(f"📞 {c.get('phone', 'Not found')}")
                st.write(f"📄 {c.get('filename', '')}")

            with d2:
                st.markdown("**Scores**")
                exp_val = c.get("experience_score")
                edu_val = c.get("education_score")
                st.write(f"Skill match    : **{_fmt(c.get('skill_score'))}%**")
                st.write(f"JD similarity  : **{_fmt(c.get('similarity_score'))}%**")
                if exp_val is None:
                    st.write("Experience     : **Not Assessed** ℹ️")
                else:
                    st.write(f"Experience     : **{_fmt(exp_val)}%**")
                if edu_val is None:
                    st.write("Education      : **Not Assessed** ℹ️")
                else:
                    st.write(f"Education      : **{_fmt(edu_val)}%**")
                st.write(f"**Final Score  : {score:.1f}%**")
                # Show score basis note when any component was excluded
                basis = c.get("score_basis", "")
                if "Not Assessed" in basis:
                    st.caption(f"ℹ️ {basis}")

            with d3:
                st.markdown("**Skills**")
                matched = c.get("matched_skills", [])
                missing = c.get("missing_skills", [])
                if matched:
                    st.write("✅ Matched: " + ", ".join(matched))
                else:
                    st.write("✅ Matched: None")
                if missing:
                    st.write("❌ Missing: " + ", ".join(missing))
                else:
                    st.write("❌ Missing: None")

            st.markdown("**Notes**")
            st.caption(f"Experience: {c.get('experience_reason', '')}")
            st.caption(f"Education: {c.get('education_reason', '')}")
            st.info(f"**Recommendation: {rec}** — This is a suggestion only. Human review required.")


    # ---------------------------------------------------------------------------
    # Section 6: Recommendations summary
    # ---------------------------------------------------------------------------

    st.markdown('<p class="section-header">🎯 Section 4: Shortlisting Recommendations</p>',
                unsafe_allow_html=True)

    tab1, tab2, tab3 = st.tabs(["✅ Shortlisted", "🔍 Manual Review", "❌ Not Shortlisted"])

    with tab1:
        sl = get_shortlisted(ranked_candidates)
        if sl:
            for c in sl:
                st.write(f"**#{c['rank']} {c.get('name')}** — {c.get('final_score', 0):.1f}%")
        else:
            st.info("No candidates met the shortlisting threshold.")

    with tab2:
        mr = get_manual_review(ranked_candidates)
        if mr:
            for c in mr:
                st.write(f"**#{c['rank']} {c.get('name')}** — {c.get('final_score', 0):.1f}%")
        else:
            st.info("No candidates flagged for manual review.")

    with tab3:
        ns = get_not_shortlisted(ranked_candidates)
        if ns:
            for c in ns:
                st.write(f"**#{c['rank']} {c.get('name')}** — {c.get('final_score', 0):.1f}%")
        else:
            st.info("All candidates met at least the manual review threshold.")

    st.warning(
        "⚠️ All recommendations above are algorithmic suggestions based on text matching. "
        "They do not account for factors such as culture fit, interview performance, or "
        "portfolio quality. Always review candidates holistically before making any decision."
    )


    # ---------------------------------------------------------------------------
    # Section 7: CSV Download
    # ---------------------------------------------------------------------------

    st.markdown('<p class="section-header">📥 Section 5: Download Report</p>', unsafe_allow_html=True)

    # Build CSV in memory
    output = io.StringIO()
    columns = [
        "Rank", "Name", "Email", "Phone", "Filename",
        "Extracted Skills", "Matched Skills", "Missing Skills",
        "Skill Score (%)", "Similarity Score (%)",
        "Experience Score (%)", "Education Score (%)",
        "Final Score (%)", "Recommendation",
        "Score Basis", "Experience Notes", "Education Notes",
    ]
    writer = csv.DictWriter(output, fieldnames=columns)
    writer.writeheader()

    def _csv_score(val):
        return "Not Assessed" if val is None else round(float(val), 2)

    for c in ranked_candidates:
        writer.writerow({
            "Rank"                  : c.get("rank", ""),
            "Name"                  : c.get("name", ""),
            "Email"                 : c.get("email", ""),
            "Phone"                 : c.get("phone", ""),
            "Filename"              : c.get("filename", ""),
            "Extracted Skills"      : "; ".join(c.get("extracted_skills", [])),
            "Matched Skills"        : "; ".join(c.get("matched_skills", [])),
            "Missing Skills"        : "; ".join(c.get("missing_skills", [])),
            "Skill Score (%)"       : _csv_score(c.get("skill_score")),
            "Similarity Score (%)"  : _csv_score(c.get("similarity_score")),
            "Experience Score (%)"  : _csv_score(c.get("experience_score")),
            "Education Score (%)"   : _csv_score(c.get("education_score")),
            "Final Score (%)"       : _csv_score(c.get("final_score")),
            "Recommendation"        : c.get("recommendation", ""),
            "Score Basis"           : c.get("score_basis", ""),
            "Experience Notes"      : c.get("experience_reason", ""),
            "Education Notes"       : c.get("education_reason", ""),
        })

    csv_bytes = output.getvalue().encode("utf-8")

    st.download_button(
        label     = "⬇️ Download Screening Report (CSV)",
        data      = csv_bytes,
        file_name = "screening_report.csv",
        mime      = "text/csv",
        help      = "Download the full candidate screening report as a CSV file.",
    )

    st.caption("The CSV report includes all candidate scores, skill matches, and recommendations.")
