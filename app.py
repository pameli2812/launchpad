import streamlit as st
import json
import hashlib
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any

from utils.parser import extract_text_from_pdf, extract_text_from_docx
from utils.matcher import calculate_match
from utils.goal_inference import auto_infer_goals_from_resume
from utils.jd_extraction import extract_jd
from utils.scorecard import analyze_scorecard
from utils.resume_suggestions import generate_resume_suggestions
from utils.verify_loop import verify_and_rescore
from utils.models import GoalSet, HistoryEntry, Goal
from utils.pdf_viewer import convert_pdf_to_images

st.set_page_config(
    page_title="AI Resume Analyzer v2",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "resume_text" not in st.session_state:
    st.session_state.resume_text = None
if "resume_filename" not in st.session_state:
    st.session_state.resume_filename = None
if "goal_sets" not in st.session_state:
    st.session_state.goal_sets = {}
if "active_goal_set_id" not in st.session_state:
    st.session_state.active_goal_set_id = None
if "history" not in st.session_state:
    st.session_state.history = []
if "draft_queue" not in st.session_state:
    st.session_state.draft_queue = []
if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = None
if "verify_attempts" not in st.session_state:
    st.session_state.verify_attempts = []
if "show_pdf_viewer" not in st.session_state:
    st.session_state.show_pdf_viewer = False
if "resume_pdf_bytes" not in st.session_state:
    st.session_state.resume_pdf_bytes = None


def get_resume_hash(text: str) -> str:
    """Generate hash of resume for snapshot comparison."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def get_active_goal_set() -> Optional[GoalSet]:
    """Get currently active goal set."""
    if not st.session_state.active_goal_set_id:
        return None
    return st.session_state.goal_sets.get(st.session_state.active_goal_set_id)


# Top bar with resume display
col1, col2, col3 = st.columns([2, 4, 2])
with col1:
    st.title("📄 Resume AI v2")
with col2:
    if st.session_state.resume_text:
        with st.container():
            st.success(f"✓ Resume: {st.session_state.resume_filename}")
    else:
        st.info("No resume loaded yet")
with col3:
    if st.button("📁 Upload", key="resume_button"):
        st.session_state.show_resume_upload = True


# Main tabs
tab1, tab2, tab3 = st.tabs(["Setup", "Analyze", "History"])

# ============ SETUP TAB ============
with tab1:
    st.header("Step 1: Upload Resume")
    
    uploaded_file = st.file_uploader("Upload your resume", type=["pdf", "docx"])
    if uploaded_file:
        try:
            if uploaded_file.type == "application/pdf":
                resume_text = extract_text_from_pdf(uploaded_file)
                # Store file bytes for PDF viewer
                st.session_state.resume_pdf_bytes = uploaded_file.getvalue()
            else:
                resume_text = extract_text_from_docx(uploaded_file)
                st.session_state.resume_pdf_bytes = None
            
            st.session_state.resume_text = resume_text
            st.session_state.resume_filename = uploaded_file.name
            st.success(f"✓ Uploaded: {uploaded_file.name}")
            
            # Display PDF or text preview
            if uploaded_file.type == "application/pdf" and st.session_state.resume_pdf_bytes:
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write("**PDF Preview:**")
                with col2:
                    if st.button("Show Full PDF"):
                        st.session_state.show_pdf_viewer = True
                
                if st.session_state.get("show_pdf_viewer", False):
                    try:
                        images = convert_pdf_to_images(st.session_state.resume_pdf_bytes)
                        page_num = st.number_input("Page", 1, len(images), 1)
                        st.image(images[page_num - 1], use_column_width=True)
                        st.caption(f"Page {page_num} of {len(images)}")
                    except Exception as e:
                        st.error(f"Error displaying PDF: {str(e)}")
                        st.write("Showing text preview instead:")
                        st.text_area("Resume text", resume_text[:500] + "...", height=150, disabled=True)
            else:
                with st.expander("Preview"):
                    st.text_area("Resume text", resume_text[:500] + "...", height=150, disabled=True)
        except Exception as e:
            st.error(f"Error parsing resume: {str(e)}")
    
    st.divider()
    st.header("Step 2: Set Career Goals")
    
    if st.session_state.resume_text:
        col1, col2 = st.columns(2)
        
        with col1:
            goal_set_name = st.text_input("Goal set name (e.g., 'Senior AI roles')")
        
        with col2:
            goal_input_mode = st.radio("How to set goals?", ["Manual", "Auto-infer"])
        
        goals = []
        
        if goal_input_mode == "Auto-infer":
            if st.button("🤖 Auto-infer from resume"):
                with st.spinner("Inferring goals..."):
                    try:
                        inferred = auto_infer_goals_from_resume(st.session_state.resume_text)
                        st.session_state.auto_inferred_goals = inferred
                        st.success("✓ Goals inferred!")
                    except Exception as e:
                        st.error(f"Error: {str(e)}")
            
            if "auto_inferred_goals" in st.session_state:
                goals = st.session_state.auto_inferred_goals
                st.info("Review auto-inferred goals:")
                for i, g in enumerate(goals):
                    st.caption(f"{i+1}. {g['label']}: {g['description']}")
        else:
            num_goals = st.number_input("Number of goals", 1, 7, 3)
            for i in range(num_goals):
                col1, col2 = st.columns([2, 1])
                with col1:
                    label = st.text_input(f"Goal {i+1} label", key=f"goal_label_{i}")
                with col2:
                    confidence = st.select_slider(f"Confidence", ["low", "medium", "high"], "high", key=f"goal_conf_{i}")
                desc = st.text_area(f"Goal {i+1} description", height=50, key=f"goal_desc_{i}")
                
                if label:
                    goals.append({
                        "id": f"goal_{i+1}",
                        "label": label,
                        "description": desc,
                        "confidence": confidence,
                        "auto_inferred": False
                    })
        
        if goals and goal_set_name:
            if st.button("✅ Create Goal Set", use_container_width=True):
                goal_set_id = str(uuid.uuid4())[:8]
                goal_objects = [
                    Goal(
                        id=g["id"],
                        label=g["label"],
                        description=g["description"],
                        confidence=g.get("confidence", "high"),
                        auto_inferred=g.get("auto_inferred", False)
                    )
                    for g in goals
                ]
                goal_set = GoalSet(
                    id=goal_set_id,
                    name=goal_set_name,
                    goals=goal_objects,
                    created_at=datetime.now(),
                    is_active=True
                )
                
                for gs_id, gs in st.session_state.goal_sets.items():
                    gs.is_active = False
                
                st.session_state.goal_sets[goal_set_id] = goal_set
                st.session_state.active_goal_set_id = goal_set_id
                st.success(f"✓ Created: {goal_set_name}")
                st.rerun()
    else:
        st.warning("Upload resume first")
    
    st.divider()
    st.subheader("Goal Sets")
    if st.session_state.goal_sets:
        for gs_id, goal_set in st.session_state.goal_sets.items():
            col1, col2, col3 = st.columns([3, 1, 1])
            with col1:
                st.write(f"**{goal_set.name}** ({len(goal_set.goals)} goals)")
            with col2:
                if goal_set.is_active:
                    st.badge("Active", "✓")
            with col3:
                if st.button("Delete", key=f"del_{gs_id}"):
                    del st.session_state.goal_sets[gs_id]
                    st.rerun()
    else:
        st.info("No goal sets yet")


# ============ ANALYZE TAB ============
with tab2:
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


# ============ HISTORY TAB ============
with tab3:
    st.header("History")
    if not st.session_state.history:
        st.info("No analyses yet")
    else:
        for i, entry in enumerate(st.session_state.history):
            col1, col2, col3 = st.columns([2, 1, 1])
            
            with col1:
                st.write(f"**{entry.jd_title}** @ {entry.company}")
                st.caption(f"{entry.goal_set_name} | {entry.analyzed_at.strftime('%m/%d %H:%M')}")
            
            with col2:
                st.metric("Fit", f"{entry.overall_fit:.1f}")
            
            with col3:
                icon = {"apply": "🟢", "borderline": "🟡", "skip": "🔴"}.get(entry.verdict, "❓")
                new_status = st.selectbox(
                    "Status",
                    ["draft", "pending", "applied", "skipped"],
                    index=["draft", "pending", "applied", "skipped"].index(entry.status),
                    key=f"status_{i}"
                )
                if new_status != entry.status:
                    st.session_state.history[i].status = new_status
                    st.success("✓")
            
            st.divider()
