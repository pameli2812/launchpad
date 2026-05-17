"""Analyse tab - JD analysis and resume scoring."""

import streamlit as st
import uuid
import hashlib
from datetime import datetime

from utils.jd_extraction import extract_jd
from utils.scorecard import analyze_scorecard
from utils.resume_suggestions import generate_resume_suggestions
from utils.models import HistoryEntry
from utils.storage import write_json


HISTORY_FILE = "data/history.json"


def get_resume_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def save_history_locally():
    serialized = []
    for entry in st.session_state.history:
        serialized.append({
            "jd_title": entry.jd_title,
            "company": entry.company,
            "goal_set_name": entry.goal_set_name,
            "overall_fit": entry.overall_fit,
            "verdict": entry.verdict,
            "status": entry.status,
            "analyzed_at": entry.analyzed_at.isoformat(),
        })
    write_json(HISTORY_FILE, serialized)


def render_verdict_banner(verdict: str):
    if verdict == "apply":
        st.success("Recommended — Strong match. Apply with your current resume.")
    elif verdict == "borderline":
        st.warning("Borderline — Possible match. Address gaps before applying.")
    else:
        st.error("Not Recommended — Weak match. Significant gaps exist.")
        if st.button("Proceed anyway — get best-case resume changes", key="override_btn"):
            st.session_state.force_suggestions = True


def render_scorecard_table(scores):
    score_data = []
    for s in sorted(scores, key=lambda x: x.score, reverse=True):
        if s.score >= 8:
            indicator = "High"
        elif s.score >= 6:
            indicator = "Mid"
        else:
            indicator = "Low"
        score_data.append({
            "Metric": s.dimension,
            "Score": f"{s.score:.1f}/10",
            "Level": indicator,
            "Comment": s.remark,
        })
    st.dataframe(score_data, use_container_width=True, hide_index=True)

    st.markdown(
        """
        <style>
        div[data-testid="stDataFrame"] thead tr th {
            background-color: #1e3a5f !important;
            color: white !important;
            font-weight: bold !important;
        }
        div[data-testid="stDataFrame"] tbody tr td {
            color: #1a1a2e !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_analyse_tab():

    # ─── Resume selector ──────────────────────────────────────
    library = st.session_state.get("resume_library", {})

    # Also include the currently loaded resume if not already in library
    if (
        st.session_state.resume_text
        and st.session_state.resume_filename
        and st.session_state.resume_filename not in library
    ):
        library[st.session_state.resume_filename] = {
            "text": st.session_state.resume_text,
            "pdf_bytes": st.session_state.resume_pdf_bytes,
        }

    if not library:
        st.warning("Upload a resume in the Setup tab first.")
        return

    st.header("Analyze a Job Description")

    st.subheader("Select Resume")
    resume_names = list(library.keys())
    selected_resume = st.selectbox(
        "Which resume to analyze against?",
        resume_names,
        index=resume_names.index(st.session_state.resume_filename)
        if st.session_state.resume_filename in resume_names
        else 0,
        key="analyse_resume_selector",
    )
    selected_resume_text = library[selected_resume]["text"]
    st.caption(f"Using: **{selected_resume}**")

    # ─── Goal set selector ────────────────────────────────────
    goal_sets = st.session_state.goal_sets
    if not goal_sets:
        st.warning("Create a goal set in the Setup tab first.")
        return

    st.subheader("Select Goal Set")
    gs_options = {gs_id: gs.name for gs_id, gs in goal_sets.items()}
    gs_names = list(gs_options.values())
    gs_ids = list(gs_options.keys())

    # Default to the active one if set
    default_gs_index = 0
    if st.session_state.active_goal_set_id and st.session_state.active_goal_set_id in gs_ids:
        default_gs_index = gs_ids.index(st.session_state.active_goal_set_id)

    selected_gs_name = st.selectbox(
        "Which goal set to score against?",
        gs_names,
        index=default_gs_index,
        key="analyse_goalset_selector",
    )
    selected_gs_id = gs_ids[gs_names.index(selected_gs_name)]
    selected_gs = goal_sets[selected_gs_id]
    st.caption(
        f"Goals: "
        + ", ".join(g.label for g in selected_gs.goals[:4])
        + ("..." if len(selected_gs.goals) > 4 else "")
    )

    st.divider()

    # ─── JD input ─────────────────────────────────────────────
    jd_text = st.text_area("Paste Job Description", height=280)
    jd_url = st.text_input("Job posting URL (optional)")

    col1, col2 = st.columns(2)

    with col1:
        analyze_btn = st.button("Analyze", use_container_width=True)

    with col2:
        if st.button("Clear results", use_container_width=True):
            st.session_state.current_analysis = None
            st.session_state.pop("suggestions", None)
            st.rerun()

    # ─── Run analysis ─────────────────────────────────────────
    if analyze_btn and jd_text:
        with st.spinner("Analyzing..."):
            try:
                jd_json = extract_jd(jd_text, jd_url)
                scorecard = analyze_scorecard(
                    selected_resume_text,
                    jd_json,
                    [
                        {
                            "id": g.id,
                            "label": g.label,
                            "description": g.description,
                            "confidence": g.confidence,
                        }
                        for g in selected_gs.goals
                    ],
                )
                st.session_state.current_analysis = {
                    "jd": jd_json,
                    "scorecard": scorecard,
                    "resume_original": selected_resume_text,
                    "resume_hash": get_resume_hash(selected_resume_text),
                    "resume_name": selected_resume,
                    "goal_set_id": selected_gs_id,
                    "goal_set_name": selected_gs.name,
                }
                st.success("Analysis complete.")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    # ─── Results ──────────────────────────────────────────────
    if not st.session_state.current_analysis:
        return

    analysis = st.session_state.current_analysis
    scorecard = analysis["scorecard"]
    jd = analysis["jd"]

    st.divider()

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Overall Fit", f"{scorecard.overall_fit:.1f}/10")
    with col2:
        st.metric("Role", jd.get("title", "?")[:40])
    with col3:
        st.metric("Company", jd.get("company", "?")[:30])

    render_verdict_banner(scorecard.verdict)
    st.divider()

    st.subheader("Summary")
    st.info(scorecard.summary)
    st.divider()

    st.subheader("Scorecard")
    render_scorecard_table(scorecard.scores)

    if scorecard.gaps:
        st.divider()
        st.subheader("Gaps to Address")
        for gap in scorecard.gaps:
            st.write(f"- {gap}")

    st.divider()

    show_suggestions = (
        scorecard.verdict in ("apply", "borderline")
        or st.session_state.get("force_suggestions", False)
    )

    col1, col2, col3 = st.columns(3)

    # ─── Get suggestions ──────────────────────────────────────
    with col1:
        if show_suggestions and st.button("Get Suggestions", use_container_width=True):
            with st.spinner("Generating suggestions..."):
                try:
                    sugg = generate_resume_suggestions(
                        selected_resume_text,
                        jd,
                        scorecard.gaps,
                        override=(scorecard.verdict == "skip"),
                    )
                    if sugg is None:
                        sugg = {"paraphrasing": [], "missing": []}
                    st.session_state.suggestions = sugg
                except Exception as e:
                    st.error(f"Suggestion generation failed: {str(e)}")
                    st.session_state.suggestions = {"paraphrasing": [], "missing": []}

    # ─── Save to history ──────────────────────────────────────
    with col2:
        if st.button("Save to History", use_container_width=True):
            entry = HistoryEntry(
                jd_id=str(uuid.uuid4())[:8],
                analyzed_at=datetime.now(),
                goal_set_id=analysis.get("goal_set_id", selected_gs_id),
                goal_set_name=analysis.get("goal_set_name", selected_gs.name),
                goal_set_snapshot=[g.to_dict() for g in selected_gs.goals],
                resume_id=analysis.get("resume_name", selected_resume),
                resume_snapshot_hash=analysis["resume_hash"],
                scorecard=scorecard.to_dict(),
                verdict=scorecard.verdict,
                overall_fit=scorecard.overall_fit,
                status="pending",
                jd_title=jd.get("title", "?"),
                company=jd.get("company", "?"),
                url=jd.get("url"),
            )
            st.session_state.history.append(entry)
            save_history_locally()
            st.success("Saved to history.")

    # ─── Download suggestions ─────────────────────────────────
    with col3:
        if "suggestions" in st.session_state:
            sugg = st.session_state.suggestions
            output = "RESUME IMPROVEMENT SUGGESTIONS\n" + "=" * 50 + "\n\n"
            if sugg.get("paraphrasing"):
                output += "PARAPHRASE:\n"
                for p in sugg["paraphrasing"]:
                    output += f"OLD: {p['original']}\nNEW: {p['improved']}\n\n"
            if sugg.get("missing"):
                output += "ADD TO RESUME:\n"
                for m in sugg["missing"]:
                    output += f"- {m['what_to_add']}\n"
            st.download_button(
                label="Download Suggestions",
                data=output,
                file_name="suggestions.txt",
                mime="text/plain",
                use_container_width=True,
            )

    # ─── Render suggestions ───────────────────────────────────
    if "suggestions" in st.session_state and show_suggestions:
        sugg = st.session_state.suggestions
        if sugg is None:
            st.warning("No suggestions could be generated.")
            return
        if not isinstance(sugg, dict):
            st.error("Invalid suggestions response.")
            return

        st.divider()
        st.subheader("Resume Change Suggestions")

        if sugg.get("paraphrasing"):
            st.markdown("**Reword existing content:**")
            for p in sugg["paraphrasing"]:
                st.caption(p.get("section", "?"))
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(
                        f"<div style='background:#fff1f2; padding:10px; border-radius:6px; "
                        f"color:#991b1b; font-size:0.9rem;'>"
                        f"<strong>Before:</strong><br>{p['original']}</div>",
                        unsafe_allow_html=True,
                    )
                with col_b:
                    st.markdown(
                        f"<div style='background:#f0fdf4; padding:10px; border-radius:6px; "
                        f"color:#166534; font-size:0.9rem;'>"
                        f"<strong>After:</strong><br>{p['improved']}</div>",
                        unsafe_allow_html=True,
                    )
                st.divider()

        if sugg.get("missing"):
            st.markdown("**Add to your resume:**")
            for m in sugg["missing"]:
                st.warning(
                    f"**{m.get('section', '?')}** — {m['what_to_add']}"
                )
