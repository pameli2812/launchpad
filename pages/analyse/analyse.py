"""Analyse tab - JD analysis and resume scoring."""

import streamlit as st
import uuid
import hashlib
from datetime import datetime

from utils.jd_extraction import extract_jd
from utils.scorecard import analyze_scorecard
from utils.resume_suggestions import generate_resume_suggestions
from utils.models import HistoryEntry


def get_resume_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def get_active_goal_set():
    if not st.session_state.active_goal_set_id:
        return None
    return st.session_state.goal_sets.get(st.session_state.active_goal_set_id)


def render_verdict_banner(verdict: str):
    if verdict == "apply":
        st.success("✅  **RECOMMENDED — Strong match. Apply with your current resume.**")
    elif verdict == "borderline":
        st.warning("⚠️  **BORDERLINE — Possible match. Address the gaps below before applying.**")
    else:
        st.error("🚫  **NOT RECOMMENDED — Weak match. Significant gaps exist.**")
        if st.button("Proceed anyway — get best-case resume changes", key="override_btn"):
            st.session_state.force_suggestions = True


def render_scorecard_table(scores):
    sorted_scores = sorted(scores, key=lambda s: s.score, reverse=True)

    rows = ""
    for s in sorted_scores:
        val = f"{s.score:.1f}"
        if s.score >= 8:
            score_cell = f"<td style='text-align:center;color:#2d6a4f;font-weight:600;padding:9px 12px;'>{val}</td>"
        elif s.score >= 6:
            score_cell = f"<td style='text-align:center;color:#854F0B;font-weight:600;padding:9px 12px;'>{val}</td>"
        else:
            score_cell = f"<td style='text-align:center;color:#A32D2D;font-weight:600;padding:9px 12px;'>{val}</td>"

        rows += f"""
        <tr style='border-bottom:0.5px solid #e8e8e8;'>
            <td style='padding:9px 12px;font-weight:500;'>{s.dimension}</td>
            {score_cell}
            <td style='padding:9px 12px;color:#555;font-size:13px;'>{s.remark}</td>
        </tr>"""

    st.markdown(f"""
    <table style='width:100%;border-collapse:collapse;font-size:14px;margin-top:4px;'>
        <thead>
            <tr style='border-bottom:2px solid #ddd;background:#fafafa;'>
                <th style='text-align:left;padding:9px 12px;width:22%;'>Metric</th>
                <th style='text-align:center;padding:9px 12px;width:10%;'>Score</th>
                <th style='text-align:left;padding:9px 12px;'>Comment</th>
            </tr>
        </thead>
        <tbody>{rows}</tbody>
    </table>
    """, unsafe_allow_html=True)


def render_analyse_tab():
    if not st.session_state.resume_text:
        st.warning("Upload resume in Setup first")
        return

    if not get_active_goal_set():
        st.warning("Create a goal set in Setup first")
        return

    active_gs = get_active_goal_set()
    st.header("Analyze JD")

    col1, col2 = st.columns([1, 3])
    with col1:
        st.write(f"**Active:** {active_gs.name}")
    with col2:
        goals_str = ", ".join([g.label for g in active_gs.goals[:3]])
        st.caption(f"Goals: {goals_str}{'...' if len(active_gs.goals) > 3 else ''}")

    st.divider()

    jd_text = st.text_area("Paste Job Description", height=300)
    jd_url = st.text_input("URL (optional)")

    col1, col2 = st.columns(2)
    with col1:
        analyze_btn = st.button("🔍 Analyze", use_container_width=True)
    with col2:
        if st.button("Clear", use_container_width=True):
            st.session_state.current_analysis = None
            st.session_state.pop("suggestions", None)
            st.session_state.pop("force_suggestions", None)
            st.rerun()

    if analyze_btn and jd_text:
        with st.spinner("Analyzing..."):
            try:
                jd_json = extract_jd(jd_text, jd_url)
                scorecard = analyze_scorecard(
                    st.session_state.resume_text,
                    jd_json,
                    [{"id": g.id, "label": g.label, "description": g.description, "confidence": g.confidence}
                     for g in active_gs.goals]
                )
                st.session_state.current_analysis = {
                    "jd": jd_json,
                    "scorecard": scorecard,
                    "resume_original": st.session_state.resume_text,
                    "resume_hash": get_resume_hash(st.session_state.resume_text)
                }
                st.session_state.pop("suggestions", None)
                st.session_state.pop("force_suggestions", None)
                st.success("✓ Analysis done!")
                st.rerun()
            except Exception as e:
                st.error(f"Error: {str(e)}")

    if st.session_state.current_analysis:
        analysis = st.session_state.current_analysis
        scorecard = analysis["scorecard"]
        jd = analysis["jd"]

        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            st.metric("Overall Fit", f"{scorecard.overall_fit:.1f} / 10")
        with col2:
            st.metric("Role", jd.get("title", "?")[:40])

        render_verdict_banner(scorecard.verdict)

        st.divider()

        st.subheader("Summary")
        st.info(scorecard.summary)

        st.divider()

        st.subheader("Scorecard")
        render_scorecard_table(scorecard.scores)

        if scorecard.gaps:
            st.divider()
            st.subheader("Gaps to address")
            for gap in scorecard.gaps:
                st.write(f"• {gap}")

        st.divider()

        show_suggestions = (
            scorecard.verdict in ("apply", "borderline")
            or st.session_state.get("force_suggestions", False)
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            if show_suggestions:
                if st.button("💡 Get Suggestions", use_container_width=True):
                    with st.spinner("Generating..."):
                        sugg = generate_resume_suggestions(
                            st.session_state.resume_text,
                            jd,
                            scorecard.gaps,
                            override=scorecard.verdict == "skip"
                        )
                        st.session_state.suggestions = sugg

        with col2:
            if st.button("💾 Save to History", use_container_width=True):
                active_gs = get_active_goal_set()
                entry = HistoryEntry(
                    jd_id=str(uuid.uuid4())[:8],
                    analyzed_at=datetime.now(),
                    goal_set_id=active_gs.id,
                    goal_set_name=active_gs.name,
                    goal_set_snapshot=[g.to_dict() for g in active_gs.goals],
                    resume_id="current",
                    resume_snapshot_hash=analysis["resume_hash"],
                    scorecard=scorecard.to_dict(),
                    verdict=scorecard.verdict,
                    overall_fit=scorecard.overall_fit,
                    status="pending",
                    jd_title=jd.get("title", "?"),
                    company=jd.get("company", "?"),
                    url=jd.get("url")
                )
                st.session_state.history.append(entry)
                st.success("✓ Saved")

        with col3:
            if "suggestions" in st.session_state and st.button("📥 Download", use_container_width=True):
                sugg = st.session_state.suggestions
                output = "RESUME IMPROVEMENT SUGGESTIONS\n" + "=" * 50 + "\n\n"
                if sugg.get("paraphrasing"):
                    output += "PARAPHRASE:\n"
                    for p in sugg["paraphrasing"]:
                        output += f"OLD: {p['original']}\nNEW: {p['improved']}\n\n"
                if sugg.get("missing"):
                    output += "ADD TO RESUME:\n"
                    for m in sugg["missing"]:
                        output += f"• {m['what_to_add']}\n"
                st.download_button("Download", output, "suggestions.txt", "text/plain")

        if "suggestions" in st.session_state and show_suggestions:
            sugg = st.session_state.suggestions
            st.divider()
            st.subheader("Resume change suggestions")

            if sugg.get("override_context"):
                st.warning(sugg["override_context"])

            if sugg.get("paraphrasing"):
                st.markdown("**Paraphrasing — ATS & impact improvements**")
                for p in sugg["paraphrasing"]:
                    st.caption(f"Section: {p.get('section', '?')}")
                    st.markdown(f"~~{p['original']}~~")
                    st.markdown(f"→ {p['improved']}")
                    st.caption(p.get("reason", ""))
                    st.divider()

            if sugg.get("missing"):
                st.markdown("**Missing — add to resume**")
                for m in sugg["missing"]:
                    st.warning(f"**{m.get('section', '?')}** — {m['what_to_add']}\n\n_{m.get('why_it_matters', '')}_")