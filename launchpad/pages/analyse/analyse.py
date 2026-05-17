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
from utils.pdf_viewer import get_uploaded_pdfs, load_pdf_bytes


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


def _ensure_resume_library():
    """Rebuild resume library from disk if session is fresh (new browser tab)."""
    if "resume_library" not in st.session_state:
        st.session_state.resume_library = {}

    if not st.session_state.resume_library:
        try:
            saved_pdfs = get_uploaded_pdfs()
        except Exception:
            saved_pdfs = []

        for pdf_info in saved_pdfs:
            name = pdf_info["name"]
            try:
                pdf_bytes = load_pdf_bytes(pdf_info["path"])
                from io import BytesIO
                from utils.parser import extract_text_from_pdf
                text = extract_text_from_pdf(BytesIO(pdf_bytes))
                st.session_state.resume_library[name] = {
                    "text": text,
                    "pdf_bytes": pdf_bytes,
                }
            except Exception:
                pass

        if st.session_state.resume_library and not st.session_state.get("resume_text"):
            first_name = list(st.session_state.resume_library.keys())[0]
            st.session_state.resume_text = st.session_state.resume_library[first_name]["text"]
            st.session_state.resume_filename = first_name


def _ensure_goal_sets():
    """Reload goal sets from disk if session is fresh (new browser tab)."""
    if not st.session_state.get("goal_sets"):
        from utils.storage import read_json
        from utils.models import Goal, GoalSet

        GOAL_SETS_FILE = "data/goal_sets.json"
        data = read_json(
            GOAL_SETS_FILE,
            default={"goal_sets": [], "active_goal_set_id": None},
        )
        goal_sets = {}
        for gs in data.get("goal_sets", []):
            goal_objects = [
                Goal(
                    id=g["id"],
                    label=g["label"],
                    description=g["description"],
                    auto_inferred=g.get("auto_inferred", False),
                )
                for g in gs["goals"]
            ]
            goal_set = GoalSet(
                id=gs["id"],
                name=gs["name"],
                goals=goal_objects,
                created_at=datetime.fromisoformat(gs["created_at"]),
                is_active=gs["is_active"],
            )
            goal_sets[gs["id"]] = goal_set

        st.session_state.goal_sets = goal_sets
        st.session_state.active_goal_set_id = data.get("active_goal_set_id")


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
        level = "High" if s.score >= 8 else ("Mid" if s.score >= 6 else "Low")
        score_data.append({
            "Metric": s.dimension,
            "Score": f"{s.score:.1f}/10",
            "Level": level,
            "Comment": s.remark,
        })
    st.dataframe(score_data, use_container_width=True, hide_index=True)
    st.markdown(
        """
        <style>
        div[data-testid="stDataFrame"] thead tr th {
            background-color: #1e3a5f !important;
            color: #ffffff !important;
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

    _ensure_resume_library()
    _ensure_goal_sets()

    library = st.session_state.get("resume_library", {})
    goal_sets = st.session_state.get("goal_sets", {})

    if not library:
        st.warning("No resumes found. Upload a resume in the Setup tab first.")
        return

    if not goal_sets:
        st.warning("No goal sets found. Create one in the Setup tab first.")
        return

    st.header("Analyze a Job Description")

    # ── Resume selector ───────────────────────────────────────
    st.subheader("Resume")
    resume_names = list(library.keys())
    default_resume_idx = 0
    if st.session_state.get("resume_filename") in resume_names:
        default_resume_idx = resume_names.index(st.session_state.resume_filename)

    selected_resume = st.selectbox(
        "Select resume to analyze against",
        resume_names,
        index=default_resume_idx,
        key="analyse_resume_selector",
    )
    selected_resume_text = library[selected_resume]["text"]

    # ── Goal set selector ─────────────────────────────────────
    st.subheader("Goal Set")
    gs_ids = list(goal_sets.keys())
    gs_names = [goal_sets[i].name for i in gs_ids]

    default_gs_idx = 0
    active_id = st.session_state.get("active_goal_set_id")
    if active_id and active_id in gs_ids:
        default_gs_idx = gs_ids.index(active_id)

    selected_gs_name = st.selectbox(
        "Select goal set to score against",
        gs_names,
        index=default_gs_idx,
        key="analyse_goalset_selector",
    )
    selected_gs_id = gs_ids[gs_names.index(selected_gs_name)]
    selected_gs = goal_sets[selected_gs_id]

    active_gs = goal_sets.get(active_id) if active_id else None
    if active_gs:
        if selected_gs_id == active_id:
            st.caption("This is your active goal set.")
        else:
            st.caption(f"Active goal set: {active_gs.name}. You're analyzing with a different one.")
    else:
        st.caption("No goal set is currently active. You can still run analysis.")

    st.divider()

    # ── JD input ──────────────────────────────────────────────
    jd_text = st.text_area("Paste Job Description", height=280, key="jd_text_input")
    jd_url = st.text_input("Job posting URL (optional)", key="jd_url_input")

    col1, col2 = st.columns(2)
    with col1:
        analyze_btn = st.button("Analyze", use_container_width=True, key="analyze_btn")
    with col2:
        if st.button("Clear results", use_container_width=True, key="clear_btn"):
            st.session_state.current_analysis = None
            st.session_state.pop("suggestions", None)
            st.rerun()

    # ── Run analysis ──────────────────────────────────────────
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
                            "confidence": "high",
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
                # Clear stale suggestions when a new analysis runs
                st.session_state.pop("suggestions", None)
                st.success("Analysis complete.")
                st.rerun()
            except Exception as e:
                st.error(str(e))

    elif analyze_btn and not jd_text:
        st.warning("Paste a job description first.")

    # ── Results ───────────────────────────────────────────────
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

    # ── Get suggestions ───────────────────────────────────────
    with col1:
        if show_suggestions and st.button("Get Suggestions", use_container_width=True, key="sugg_btn"):
            with st.spinner("Generating suggestions..."):
                try:
                    sugg = generate_resume_suggestions(
                        selected_resume_text,
                        jd,
                        scorecard.gaps,
                        override=(scorecard.verdict == "skip"),
                    )
                    # Always store a valid dict — never None
                    if not sugg or not isinstance(sugg, dict):
                        sugg = {"paraphrasing": [], "missing": []}
                    st.session_state.suggestions = sugg
                except Exception as e:
                    st.error(f"Suggestion generation failed: {e}")
                    st.session_state.suggestions = {"paraphrasing": [], "missing": []}

    # ── Save to history ───────────────────────────────────────
    with col2:
        if st.button("Save to History", use_container_width=True, key="save_hist_btn"):
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

    # ── Download suggestions ──────────────────────────────────
    with col3:
        # Guard: only show download if suggestions exist and are a valid dict
        sugg_for_dl = st.session_state.get("suggestions")
        if sugg_for_dl and isinstance(sugg_for_dl, dict):
            output = "RESUME IMPROVEMENT SUGGESTIONS\n" + "=" * 50 + "\n\n"
            if sugg_for_dl.get("paraphrasing"):
                output += "PARAPHRASE:\n"
                for p in sugg_for_dl["paraphrasing"]:
                    output += f"OLD: {p.get('original', '')}\nNEW: {p.get('improved', '')}\n\n"
            if sugg_for_dl.get("missing"):
                output += "ADD TO RESUME:\n"
                for m in sugg_for_dl["missing"]:
                    output += f"- {m.get('what_to_add', '')}\n"
            st.download_button(
                label="Download Suggestions",
                data=output,
                file_name="suggestions.txt",
                mime="text/plain",
                use_container_width=True,
                key="dl_sugg_btn",
            )

    # ── Suggestions display ───────────────────────────────────
    sugg = st.session_state.get("suggestions")
    if sugg and isinstance(sugg, dict) and show_suggestions:
        st.divider()
        st.subheader("Resume Change Suggestions")

        if sugg.get("paraphrasing"):
            st.markdown("**Reword existing content:**")
            for p in sugg["paraphrasing"]:
                st.caption(p.get("section", "?"))
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown(
                        f"<div style='background:#fff1f2;padding:10px;border-radius:6px;"
                        f"color:#991b1b;font-size:0.9rem;'>"
                        f"<strong>Before:</strong><br>{p.get('original', '')}</div>",
                        unsafe_allow_html=True,
                    )
                with col_b:
                    st.markdown(
                        f"<div style='background:#f0fdf4;padding:10px;border-radius:6px;"
                        f"color:#166534;font-size:0.9rem;'>"
                        f"<strong>After:</strong><br>{p.get('improved', '')}</div>",
                        unsafe_allow_html=True,
                    )
                st.divider()

        if sugg.get("missing"):
            st.markdown("**Add to your resume:**")
            for m in sugg["missing"]:
                st.warning(f"**{m.get('section', '?')}** — {m.get('what_to_add', '')}")