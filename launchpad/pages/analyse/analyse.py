"""Analyse tab - JD analysis and resume scoring."""

import streamlit as st
import uuid
import hashlib
from datetime import datetime
from io import BytesIO

from utils.jd_extraction import extract_jd
from utils.scorecard import analyze_scorecard
from utils.resume_suggestions import generate_resume_suggestions
from utils.models import HistoryEntry
from utils.storage import write_json
from utils.pdf_viewer import get_uploaded_pdfs, load_pdf_bytes


HISTORY_FILE = "data/history.json"


def get_resume_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def _auto_save_history(analysis, scorecard, jd, selected_gs, selected_resume):
    """Auto-save to history immediately after analysis completes."""
    entry = HistoryEntry(
        jd_id=str(uuid.uuid4())[:8],
        analyzed_at=datetime.now(),
        goal_set_id=analysis.get("goal_set_id", ""),
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
    if not hasattr(st.session_state, "history") or st.session_state.history is None:
        st.session_state.history = []
    st.session_state.history.append(entry)
    serialized = []
    for e in st.session_state.history:
        serialized.append({
            "jd_title": e.jd_title, "company": e.company,
            "goal_set_name": e.goal_set_name, "overall_fit": e.overall_fit,
            "verdict": e.verdict, "status": e.status,
            "analyzed_at": e.analyzed_at.isoformat(),
        })
    write_json(HISTORY_FILE, serialized)


def _ensure_resume_library():
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
                from utils.parser import extract_text_from_pdf
                text = extract_text_from_pdf(BytesIO(pdf_bytes))
                st.session_state.resume_library[name] = {"text": text, "pdf_bytes": pdf_bytes}
            except Exception:
                pass
        if st.session_state.resume_library and not st.session_state.get("resume_text"):
            first = list(st.session_state.resume_library.keys())[0]
            st.session_state.resume_text = st.session_state.resume_library[first]["text"]
            st.session_state.resume_filename = first


def _ensure_goal_sets():
    if not st.session_state.get("goal_sets"):
        from utils.storage import read_json
        from utils.models import Goal, GoalSet
        data = read_json("data/goal_sets.json", default={"goal_sets": [], "active_goal_set_id": None})
        goal_sets = {}
        for gs in data.get("goal_sets", []):
            goal_objects = [
                Goal(id=g["id"], label=g["label"], description=g["description"], auto_inferred=g.get("auto_inferred", False))
                for g in gs["goals"]
            ]
            goal_set = GoalSet(
                id=gs["id"], name=gs["name"], goals=goal_objects,
                created_at=datetime.fromisoformat(gs["created_at"]), is_active=gs["is_active"],
            )
            goal_sets[gs["id"]] = goal_set
        st.session_state.goal_sets = goal_sets
        st.session_state.active_goal_set_id = data.get("active_goal_set_id")


def render_verdict_banner(verdict: str):
    if verdict == "apply":
        st.success("Strong match — recommended to apply with your current resume.")
    elif verdict == "borderline":
        st.warning("Borderline match — address gaps before applying.")
    else:
        st.error("Weak match — significant gaps exist.")
        if st.button("Proceed anyway and get suggestions", key="override_btn"):
            st.session_state.force_suggestions = True
            st.rerun()


def render_scorecard_table(scores):
    score_data = []
    for s in sorted(scores, key=lambda x: x.score, reverse=True):
        level = "High" if s.score >= 8 else ("Mid" if s.score >= 6 else "Low")
        score_data.append({"Dimension": s.dimension, "Score": f"{s.score:.1f}/10", "Level": level, "Remarks": s.remark})
    st.dataframe(score_data, use_container_width=True, hide_index=True)


def render_gaps(gaps):
    """Render gaps with type / details / criticality format."""
    if not gaps:
        st.success("No significant gaps found — this JD is a strong match for your profile.")
        return

    # Try to parse structured gaps if the LLM returned them;
    # fall back to rendering raw strings with criticality inference
    for gap in gaps:
        if isinstance(gap, dict):
            gap_type = gap.get("type", "Skill Gap")
            details = gap.get("details", gap.get("description", str(gap)))
            criticality = gap.get("criticality", "Medium")
        else:
            # Raw string — infer criticality from keywords
            gap_str = str(gap)
            if any(w in gap_str.lower() for w in ["required", "must", "essential", "critical"]):
                criticality = "High"
            elif any(w in gap_str.lower() for w in ["nice", "preferred", "bonus", "plus"]):
                criticality = "Low"
            else:
                criticality = "Medium"
            gap_type = "Gap"
            details = gap_str

        color_map = {"High": "#fef2f2", "Medium": "#fffbeb", "Low": "#f0fdf4"}
        border_map = {"High": "#fca5a5", "Medium": "#fcd34d", "Low": "#86efac"}
        label_color = {"High": "#991b1b", "Medium": "#92400e", "Low": "#166534"}

        bg = color_map.get(criticality, "#f8f9fb")
        border = border_map.get(criticality, "#cbd5e1")
        lc = label_color.get(criticality, "#1a1a2e")

        st.markdown(
            f"""
            <div style='background:{bg}; border:1px solid {border}; border-radius:8px;
                        padding:12px 16px; margin-bottom:10px;'>
                <div style='display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;'>
                    <span style='font-weight:600; color:#1a1a2e;'>{gap_type}</span>
                    <span style='font-size:0.78rem; font-weight:700; color:{lc};
                                 background:{border}; padding:2px 8px; border-radius:12px;'>
                        {criticality}
                    </span>
                </div>
                <p style='margin:0; color:#374151; font-size:0.9rem;'>{details}</p>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_suggestions_table(sugg):
    """Render suggestions in a structured table: Type / Section / Before / After."""
    if not sugg or not isinstance(sugg, dict):
        st.info("No suggestions available.")
        return

    rows = []

    for p in sugg.get("paraphrasing", []):
        rows.append({
            "Type": "Text Edit",
            "Section": p.get("section", "—"),
            "Before": p.get("original", "—"),
            "After": p.get("improved", "—"),
        })

    for m in sugg.get("missing", []):
        what = m.get("what_to_add", "—")
        section = m.get("section", "—")
        rows.append({
            "Type": "Add Data",
            "Section": section,
            "Before": "No existing content",
            "After": what,
        })

    for r in sugg.get("remove", []):
        rows.append({
            "Type": "Remove Text",
            "Section": r.get("section", "—"),
            "Before": r.get("text", "—"),
            "After": "Remove this content",
        })

    for po in sugg.get("polish", []):
        rows.append({
            "Type": "Polish Content",
            "Section": po.get("section", "—"),
            "Before": po.get("original", "—"),
            "After": po.get("improved", "—"),
        })

    if not rows:
        st.info("No structured suggestions returned. Try regenerating.")
        return

    # Render as styled cards (not a flat table — Before/After can be long)
    for row in rows:
        type_colors = {
            "Text Edit": "#dbeafe",
            "Add Data": "#dcfce7",
            "Remove Text": "#fee2e2",
            "Polish Content": "#fef9c3",
        }
        type_text_colors = {
            "Text Edit": "#1e40af",
            "Add Data": "#166534",
            "Remove Text": "#991b1b",
            "Polish Content": "#854d0e",
        }
        bg = type_colors.get(row["Type"], "#f1f5f9")
        tc = type_text_colors.get(row["Type"], "#1a1a2e")

        st.markdown(
            f"""
            <div style='border:1px solid #e2e8f0; border-radius:8px; margin-bottom:12px; overflow:hidden;'>
                <div style='background:{bg}; padding:8px 14px; display:flex; gap:16px; align-items:center;'>
                    <span style='font-weight:700; color:{tc}; font-size:0.82rem;'>{row["Type"]}</span>
                    <span style='color:#64748b; font-size:0.82rem;'>Section: <strong>{row["Section"]}</strong></span>
                </div>
                <div style='display:grid; grid-template-columns:1fr 1fr; gap:0;'>
                    <div style='padding:12px 14px; border-right:1px solid #e2e8f0; background:#fff1f2;'>
                        <div style='font-size:0.75rem; color:#991b1b; font-weight:600; margin-bottom:4px;'>BEFORE</div>
                        <div style='color:#374151; font-size:0.88rem;'>{row["Before"]}</div>
                    </div>
                    <div style='padding:12px 14px; background:#f0fdf4;'>
                        <div style='font-size:0.75rem; color:#166534; font-weight:600; margin-bottom:4px;'>AFTER</div>
                        <div style='color:#374151; font-size:0.88rem;'>{row["After"]}</div>
                    </div>
                </div>
            </div>
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

    # ── Resume + Goal Set selectors ───────────
    col_r, col_g = st.columns(2)
    with col_r:
        resume_names = list(library.keys())
        default_resume_idx = 0
        if st.session_state.get("resume_filename") in resume_names:
            default_resume_idx = resume_names.index(st.session_state.resume_filename)
        selected_resume = st.selectbox(
            "Resume", resume_names, index=default_resume_idx, key="analyse_resume_selector",
        )
        selected_resume_text = library[selected_resume]["text"]

    with col_g:
        gs_ids = list(goal_sets.keys())
        gs_names = [goal_sets[i].name for i in gs_ids]
        default_gs_idx = 0
        active_id = st.session_state.get("active_goal_set_id")
        if active_id and active_id in gs_ids:
            default_gs_idx = gs_ids.index(active_id)
        selected_gs_name = st.selectbox(
            "Goal Set", gs_names, index=default_gs_idx, key="analyse_goalset_selector",
        )
        selected_gs_id = gs_ids[gs_names.index(selected_gs_name)]
        selected_gs = goal_sets[selected_gs_id]

    st.divider()

    # ── JD input — text / URL / screenshot ────
    st.subheader("Job Description")
    jd_input_mode = st.radio(
        "Input method",
        ["Paste text", "URL", "Screenshot / Image"],
        horizontal=True,
        key="jd_input_mode",
    )

    jd_text = ""
    jd_url = ""

    if jd_input_mode == "Paste text":
        jd_text = st.text_area(
            "Paste the full job description",
            height=260,
            key="jd_text_input",
            placeholder="Paste the job description here...",
        )

    elif jd_input_mode == "URL":
        jd_url = st.text_input(
            "Job posting URL",
            key="jd_url_input",
            placeholder="https://...",
        )
        st.caption("The URL will be passed to the extractor. Make sure the page is publicly accessible.")

    elif jd_input_mode == "Screenshot / Image":
        jd_image = st.file_uploader(
            "Upload a screenshot of the job posting (PNG, JPG)",
            type=["png", "jpg", "jpeg"],
            key="jd_image_upload",
        )
        if jd_image:
            st.image(jd_image, caption="Uploaded JD screenshot", use_container_width=True)
            st.info("Image-based extraction will use OCR via the LLM. Accuracy depends on image quality.")
            # Convert image to base64 for LLM (stored for extraction)
            import base64
            img_bytes = jd_image.getvalue()
            st.session_state.jd_image_b64 = base64.b64encode(img_bytes).decode()
            st.session_state.jd_image_name = jd_image.name
            jd_text = f"[IMAGE_JD:{st.session_state.jd_image_name}]"  # sentinel for extractor

    # ── Analyze button ─────────────────────────
    st.divider()
    c1, c2 = st.columns([2, 1])
    with c1:
        analyze_btn = st.button("Analyze JD", use_container_width=True, key="analyze_btn", type="primary")
    with c2:
        if st.button("Start New Analysis", use_container_width=True, key="new_analysis_btn"):
            st.session_state.current_analysis = None
            st.session_state.pop("suggestions", None)
            st.session_state.force_suggestions = False
            st.rerun()

    # ── Run analysis ──────────────────────────
    if analyze_btn and (jd_text or jd_url):
        with st.spinner("Analyzing..."):
            try:
                jd_json = extract_jd(jd_text or "", jd_url or None)
                scorecard = analyze_scorecard(
                    selected_resume_text,
                    jd_json,
                    [{"id": g.id, "label": g.label, "description": g.description, "confidence": "high"}
                     for g in selected_gs.goals],
                )
                analysis = {
                    "jd": jd_json,
                    "scorecard": scorecard,
                    "resume_original": selected_resume_text,
                    "resume_hash": get_resume_hash(selected_resume_text),
                    "resume_name": selected_resume,
                    "goal_set_id": selected_gs_id,
                    "goal_set_name": selected_gs.name,
                }
                st.session_state.current_analysis = analysis
                st.session_state.pop("suggestions", None)
                st.session_state.force_suggestions = False
                # Auto-save to history immediately
                _auto_save_history(analysis, scorecard, jd_json, selected_gs, selected_resume)
                st.rerun()
            except Exception as e:
                st.error(str(e))

    elif analyze_btn and not jd_text and not jd_url:
        st.warning("Provide a job description first.")

    # ── Results ───────────────────────────────
    if not st.session_state.get("current_analysis"):
        return

    analysis = st.session_state.current_analysis
    scorecard = analysis["scorecard"]
    jd = analysis["jd"]

    st.divider()

    # Top metrics
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Overall Fit", f"{scorecard.overall_fit:.1f}/10")
    with col2:
        st.metric("Role", (jd.get("title") or "?")[:35])
    with col3:
        st.metric("Company", (jd.get("company") or "?")[:25])
    with col4:
        st.metric("Verdict", scorecard.verdict.title())

    render_verdict_banner(scorecard.verdict)
    st.divider()

    # Summary
    st.subheader("Summary")
    st.info(scorecard.summary)
    st.divider()

    # Scorecard
    st.subheader("Scorecard")
    render_scorecard_table(scorecard.scores)
    st.divider()

    # Gaps
    st.subheader("Gaps to Address")
    render_gaps(scorecard.gaps)
    st.divider()

    # ── Suggestions section ───────────────────
    show_suggestions = (
        scorecard.verdict in ("apply", "borderline")
        or st.session_state.get("force_suggestions", False)
    )

    if show_suggestions:
        st.subheader("Resume Change Suggestions")

        # User prompt for suggestions
        user_sugg_prompt = st.text_area(
            "Guide the suggestions (optional)",
            key="user_sugg_prompt",
            height=80,
            placeholder="e.g. Focus on making my AI experience more prominent. Keep changes concise. Emphasize leadership.",
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            get_sugg = st.button("Get Suggestions", use_container_width=True, key="sugg_btn")
        with c2:
            regen = st.button("Regenerate", use_container_width=True, key="regen_btn")
        with c3:
            sugg_for_dl = st.session_state.get("suggestions")
            if sugg_for_dl and isinstance(sugg_for_dl, dict):
                # Build download text
                output = "RESUME IMPROVEMENT SUGGESTIONS\n" + "=" * 50 + "\n\n"
                for p in sugg_for_dl.get("paraphrasing", []):
                    output += f"[TEXT EDIT] {p.get('section','')}\nBEFORE: {p.get('original','')}\nAFTER:  {p.get('improved','')}\n\n"
                for m in sugg_for_dl.get("missing", []):
                    output += f"[ADD DATA] {m.get('section','')}\nADD: {m.get('what_to_add','')}\n\n"
                st.download_button(
                    "Download Suggestions", data=output,
                    file_name="suggestions.txt", mime="text/plain",
                    use_container_width=True, key="dl_sugg_btn",
                )

        if get_sugg or regen:
            with st.spinner("Generating suggestions..."):
                try:
                    sugg = generate_resume_suggestions(
                        selected_resume_text, jd, scorecard.gaps,
                        override=(scorecard.verdict == "skip"),
                    )
                    if not sugg or not isinstance(sugg, dict):
                        sugg = {"paraphrasing": [], "missing": []}
                    # Inject user prompt context if provided
                    if user_sugg_prompt.strip():
                        sugg["_user_prompt"] = user_sugg_prompt.strip()
                    st.session_state.suggestions = sugg
                except Exception as e:
                    st.error(f"Suggestion generation failed: {e}")
                    st.session_state.suggestions = {"paraphrasing": [], "missing": []}

        sugg = st.session_state.get("suggestions")
        if sugg and isinstance(sugg, dict):
            render_suggestions_table(sugg)

    st.divider()
    st.caption(f"Analysis run at {datetime.now().strftime('%d %b %Y %H:%M')} · Auto-saved to history")