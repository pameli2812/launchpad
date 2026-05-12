"""Analyse tab - JD analysis and resume scoring."""

import streamlit as st
import uuid
import hashlib
from datetime import datetime
from typing import Optional

from utils.jd_extraction import extract_jd
from utils.scorecard import analyze_scorecard
from utils.resume_suggestions import generate_resume_suggestions
from utils.models import HistoryEntry


def get_resume_hash(text: str) -> str:
    """Generate hash of resume for snapshot comparison."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def get_active_goal_set():
    """Get currently active goal set."""
    if not st.session_state.active_goal_set_id:
        return None
    return st.session_state.goal_sets.get(st.session_state.active_goal_set_id)


def render_analyse_tab():
    """Render the Analyse tab content."""
    if not st.session_state.resume_text:
        st.warning("Upload resume in Setup first")
    elif not get_active_goal_set():
        st.warning("Create goal set in Setup first")
    else:
        active_gs = get_active_goal_set()
        st.header("Analyze JD")
        
        col1, col2 = st.columns([1, 3])
        with col1:
            st.write(f"**Active:** {active_gs.name}")
        with col2:
            goals_str = ", ".join([g.label for g in active_gs.goals[:3]])
            st.caption(f"Goals: {goals_str}...")
        
        st.divider()
        
        jd_text = st.text_area("Paste Job Description", height=300)
        jd_url = st.text_input("URL (optional)")
        
        col1, col2 = st.columns(2)
        with col1:
            analyze_btn = st.button("🔍 Analyze", use_container_width=True)
        with col2:
            if st.button("Clear", use_container_width=True):
                st.session_state.current_analysis = None
                st.rerun()
        
        if analyze_btn and jd_text:
            with st.spinner("Analyzing..."):
                try:
                    jd_json = extract_jd(jd_text, jd_url)
                    scorecard = analyze_scorecard(
                        st.session_state.resume_text,
                        jd_json,
                        [{"id": g.id, "label": g.label, "description": g.description, "confidence": g.confidence} for g in active_gs.goals]
                    )
                    
                    st.session_state.current_analysis = {
                        "jd": jd_json,
                        "scorecard": scorecard,
                        "resume_original": st.session_state.resume_text,
                        "resume_hash": get_resume_hash(st.session_state.resume_text)
                    }
                    st.success("✓ Analysis done!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {str(e)}")
        
        if st.session_state.current_analysis:
            analysis = st.session_state.current_analysis
            scorecard = analysis["scorecard"]
            jd = analysis["jd"]
            
            st.divider()
            
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Fit", f"{scorecard.overall_fit:.1f}/10")
            with col2:
                verdict_icon = {"apply": "🟢", "borderline": "🟡", "skip": "🔴"}
                st.metric("Verdict", verdict_icon.get(scorecard.verdict, "❓"))
            with col3:
                st.metric("Role", jd.get("title", "?")[:20])
            
            st.divider()
            st.write(scorecard.summary)
            
            st.divider()
            st.subheader("Scores")
            for score in scorecard.scores:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"**{score.dimension}**: {score.remark}")
                with col2:
                    st.metric("", f"{score.score:.1f}")
            
            if scorecard.gaps:
                st.divider()
                st.subheader("Fixable Gaps")
                for gap in scorecard.gaps:
                    st.write(f"• {gap}")
            
            st.divider()
            col1, col2, col3 = st.columns(3)
            
            with col1:
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
                if st.button("💾 Save", use_container_width=True):
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
                        status="draft",
                        jd_title=jd.get("title", "?"),
                        company=jd.get("company", "?"),
                        url=jd.get("url")
                    )
                    st.session_state.history.append(entry)
                    st.success("✓ Saved")
            
            with col3:
                if "suggestions" in st.session_state and st.button("📥 Download", use_container_width=True):
                    sugg = st.session_state.suggestions
                    output = "RESUME IMPROVEMENT SUGGESTIONS\n" + "="*50 + "\n\n"
                    if sugg.get("paraphrasing"):
                        output += "PARAPHRASE:\n"
                        for p in sugg["paraphrasing"]:
                            output += f"❌ {p['original']}\n✅ {p['improved']}\n\n"
                    if sugg.get("missing"):
                        output += "ADD TO RESUME:\n"
                        for m in sugg["missing"]:
                            output += f"• {m['what_to_add']}\n"
                    
                    st.download_button(
                        "Download", output, "suggestions.txt", "text/plain"
                    )
