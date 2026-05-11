import streamlit as st
import json
import hashlib
import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
import base64
from utils.parser import extract_text_from_pdf, extract_text_from_docx
from utils.matcher import calculate_match
from utils.goal_inference import auto_infer_goals_from_resume
from utils.jd_extraction import extract_jd
from utils.scorecard import analyze_scorecard
from utils.resume_suggestions import generate_resume_suggestions
from utils.verify_loop import verify_and_rescore
from utils.models import GoalSet, HistoryEntry, Goal
from utils.pdf_viewer import convert_pdf_to_images, extract_pdf_text_preview, save_pdf_locally, get_uploaded_pdfs, load_pdf_bytes, delete_pdf

st.set_page_config(
    page_title="AI Resume Analyzer v2",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Modern UI Overrides ────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@300;400;500;600&family=DM+Mono:wght@400;500&display=swap');

/* ── Root & base ── */
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}

/* App background */
.stApp {
    background: #0d0f14;
}

/* ── Top bar ── */
header[data-testid="stHeader"] {
    background: transparent;
}

/* ── Sidebar ── */
[data-testid="stSidebar"] {
    background: #111318 !important;
    border-right: 1px solid #1e2130;
}

/* ── Main block container ── */
.block-container {
    padding: 2rem 3rem !important;
    max-width: 1200px;
}

/* ── Typography ── */
h1 { font-size: 1.6rem !important; font-weight: 600 !important; letter-spacing: -0.5px; color: #f0f2f8 !important; }
h2 { font-size: 1.25rem !important; font-weight: 600 !important; color: #e2e6f0 !important; margin-bottom: 0.5rem !important; }
h3 { font-size: 1rem !important; font-weight: 500 !important; color: #c8cede !important; }
p, label, .stMarkdown { color: #a8b0c8 !important; font-size: 0.9rem !important; }
.stCaption { color: #5a6180 !important; font-size: 0.78rem !important; }

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"] {
    background: #111318;
    border-radius: 12px;
    padding: 4px;
    gap: 2px;
    border: 1px solid #1e2130;
}
.stTabs [data-baseweb="tab"] {
    border-radius: 9px;
    padding: 8px 22px;
    font-size: 0.85rem;
    font-weight: 500;
    color: #5a6180;
    background: transparent;
    transition: all 0.2s ease;
}
.stTabs [aria-selected="true"] {
    background: #1e2235 !important;
    color: #a5b4fc !important;
}
.stTabs [data-baseweb="tab-border"] { display: none; }

/* ── Inputs ── */
.stTextInput > div > div,
.stTextArea > div > div,
.stNumberInput > div > div > input {
    background: #13151e !important;
    border: 1px solid #1e2335 !important;
    border-radius: 10px !important;
    color: #e0e4f0 !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.88rem !important;
    padding: 10px 14px !important;
    transition: border-color 0.2s;
}
.stTextInput > div > div:focus-within,
.stTextArea > div > div:focus-within {
    border-color: #6366f1 !important;
    box-shadow: 0 0 0 3px rgba(99,102,241,0.12) !important;
}
.stTextInput input, .stTextArea textarea {
    color: #e0e4f0 !important;
}

/* ── Number input ── */
.stNumberInput [data-testid="stNumberInput-StepDown"],
.stNumberInput [data-testid="stNumberInput-StepUp"] {
    background: #1e2235 !important;
    border: none !important;
    color: #a5b4fc !important;
    border-radius: 6px !important;
}

/* ── Select slider ── */
.stSlider > div { padding: 0 !important; }
.stSlider [data-baseweb="slider"] div[role="slider"] {
    background: #6366f1 !important;
    border: 2px solid #818cf8 !important;
}
.stSlider [data-baseweb="slider"] div[data-testid="stThumbValue"] {
    color: #a5b4fc !important;
    font-size: 0.75rem !important;
    font-weight: 600 !important;
}

/* ── Buttons ── */
.stButton > button {
    background: #1e2235 !important;
    border: 1px solid #2a2f4a !important;
    border-radius: 10px !important;
    color: #c8cede !important;
    font-family: 'DM Sans', sans-serif !important;
    font-size: 0.85rem !important;
    font-weight: 500 !important;
    padding: 9px 20px !important;
    transition: all 0.2s ease !important;
}
.stButton > button:hover {
    background: #252a42 !important;
    border-color: #6366f1 !important;
    color: #e0e4f0 !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 16px rgba(99,102,241,0.15) !important;
}

/* Primary action buttons (Create Goal Set, Analyze) */
.stButton > button[kind="primary"],
div[data-testid="stButton"] > button:first-child {
    background: linear-gradient(135deg, #4f52c8, #6366f1) !important;
    border: none !important;
    color: #fff !important;
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #5a5de0, #7577f5) !important;
    box-shadow: 0 6px 20px rgba(99,102,241,0.35) !important;
}

/* Download button */
.stDownloadButton > button {
    background: #13151e !important;
    border: 1px solid #1e2335 !important;
    border-radius: 10px !important;
    color: #a8b0c8 !important;
    font-size: 0.85rem !important;
    width: 100%;
}

/* ── File uploader ── */
[data-testid="stFileUploader"] {
    background: #111318 !important;
    border: 1.5px dashed #1e2335 !important;
    border-radius: 14px !important;
    padding: 1.2rem !important;
    transition: border-color 0.2s;
}
[data-testid="stFileUploader"]:hover {
    border-color: #6366f1 !important;
}
[data-testid="stFileUploader"] label {
    color: #5a6180 !important;
    font-size: 0.85rem !important;
}

/* ── Metrics ── */
[data-testid="stMetric"] {
    background: #111318;
    border: 1px solid #1e2130;
    border-radius: 12px;
    padding: 1rem 1.2rem !important;
}
[data-testid="stMetricLabel"] { color: #5a6180 !important; font-size: 0.75rem !important; text-transform: uppercase; letter-spacing: 0.05em; }
[data-testid="stMetricValue"] { color: #e0e4f0 !important; font-size: 1.6rem !important; font-weight: 600 !important; }

/* ── Alerts (success / info / warning / error) ── */
.stSuccess, [data-testid="stNotification"][kind="success"] {
    background: rgba(16,185,129,0.08) !important;
    border: 1px solid rgba(16,185,129,0.25) !important;
    border-radius: 10px !important;
    color: #6ee7b7 !important;
}
.stInfo, [data-testid="stNotification"][kind="info"] {
    background: rgba(99,102,241,0.08) !important;
    border: 1px solid rgba(99,102,241,0.22) !important;
    border-radius: 10px !important;
    color: #a5b4fc !important;
}
.stWarning, [data-testid="stNotification"][kind="warning"] {
    background: rgba(245,158,11,0.08) !important;
    border: 1px solid rgba(245,158,11,0.25) !important;
    border-radius: 10px !important;
    color: #fcd34d !important;
}
.stError, [data-testid="stNotification"][kind="error"] {
    background: rgba(239,68,68,0.08) !important;
    border: 1px solid rgba(239,68,68,0.22) !important;
    border-radius: 10px !important;
    color: #fca5a5 !important;
}

/* ── Expander ── */
.stExpander {
    background: #111318 !important;
    border: 1px solid #1e2130 !important;
    border-radius: 12px !important;
}
.stExpander summary { color: #a8b0c8 !important; font-size: 0.88rem !important; }

/* ── Divider ── */
hr { border-color: #1e2130 !important; margin: 1.5rem 0 !important; }

/* ── Radio buttons ── */
.stRadio > div { gap: 0.6rem !important; }
.stRadio label {
    background: #111318;
    border: 1px solid #1e2130;
    border-radius: 9px;
    padding: 8px 16px !important;
    color: #a8b0c8 !important;
    font-size: 0.85rem !important;
    transition: all 0.18s;
    cursor: pointer;
}
.stRadio label:has(input:checked) {
    background: rgba(99,102,241,0.12) !important;
    border-color: #6366f1 !important;
    color: #a5b4fc !important;
}

/* ── Selectbox ── */
.stSelectbox > div > div {
    background: #13151e !important;
    border: 1px solid #1e2335 !important;
    border-radius: 10px !important;
    color: #e0e4f0 !important;
    font-size: 0.88rem !important;
}

/* ── Spinner ── */
.stSpinner > div { border-top-color: #6366f1 !important; }

/* ── Scrollbar ── */
::-webkit-scrollbar { width: 6px; height: 6px; }
::-webkit-scrollbar-track { background: #0d0f14; }
::-webkit-scrollbar-thumb { background: #1e2335; border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: #2a304d; }
</style>
""", unsafe_allow_html=True)

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
if "show_pdf_modal" not in st.session_state:
    st.session_state.show_pdf_modal = False
if "pdf_modal_bytes" not in st.session_state:
    st.session_state.pdf_modal_bytes = None
if "pdf_modal_name" not in st.session_state:
    st.session_state.pdf_modal_name = None
if "pdf_current_page" not in st.session_state:
    st.session_state.pdf_current_page = 1
if "last_uploaded_file" not in st.session_state:
    st.session_state.last_uploaded_file = None


def get_resume_hash(text: str) -> str:
    """Generate hash of resume for snapshot comparison."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def get_active_goal_set() -> Optional[GoalSet]:
    """Get currently active goal set."""
    if not st.session_state.active_goal_set_id:
        return None
    return st.session_state.goal_sets.get(st.session_state.active_goal_set_id)


import base64


@st.dialog("📄 PDF Viewer")
def pdf_viewer_modal():

    if (
        st.session_state.pdf_modal_bytes
        and st.session_state.pdf_modal_name
    ):

        st.subheader(st.session_state.pdf_modal_name)

        pdf_bytes = st.session_state.pdf_modal_bytes

        # Download button
        st.download_button(
            "⬇ Download PDF",
            data=pdf_bytes,
            file_name=st.session_state.pdf_modal_name,
            mime="application/pdf",
            use_container_width=True
        )

        st.divider()

        # Encode PDF and embed inline via iframe
        pdf_b64 = base64.b64encode(pdf_bytes).decode("utf-8")

        pdf_html = f"""
        <iframe
            src="data:application/pdf;base64,{pdf_b64}"
            width="100%"
            height="600px"
            style="border: none; border-radius: 8px;"
            type="application/pdf"
        >
        </iframe>
        """

        st.markdown(pdf_html, unsafe_allow_html=True)
# Show PDF modal if triggered
if st.session_state.show_pdf_modal:
    pdf_viewer_modal()
    # Reset the modal flag after showing
    st.session_state.show_pdf_modal = False


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
        # Only process if it's a new file (not already uploaded)
        if st.session_state.last_uploaded_file != uploaded_file.name:
            try:
                pdf_bytes = uploaded_file.getvalue()
                
                if uploaded_file.type == "application/pdf":
                    resume_text = extract_text_from_pdf(uploaded_file)
                    # Save PDF locally for persistence
                    try:
                        save_pdf_locally(pdf_bytes, uploaded_file.name)
                    except Exception as e:
                        st.warning(f"Could not save PDF locally: {str(e)}")
                    st.session_state.resume_pdf_bytes = pdf_bytes
                else:
                    resume_text = extract_text_from_docx(uploaded_file)
                    st.session_state.resume_pdf_bytes = None
                
                st.session_state.resume_text = resume_text
                st.session_state.resume_filename = uploaded_file.name
                st.session_state.last_uploaded_file = uploaded_file.name
                st.success(f"✓ Uploaded: {uploaded_file.name}")
                
            except Exception as e:
                st.error(f"Error parsing resume: {str(e)}")
        
        # Display PDF or text preview (always show after upload)
        if st.session_state.resume_text:
            if uploaded_file.type == "application/pdf" and st.session_state.resume_pdf_bytes:
                col1, col2 = st.columns([2, 1])
                with col1:
                    st.write("**PDF Preview:**")
                with col2:
                    if st.button("📖 Open in Viewer", key="open_pdf_btn"):
                        st.session_state.show_pdf_modal = True
                        st.session_state.pdf_modal_bytes = st.session_state.resume_pdf_bytes
                        st.session_state.pdf_modal_name = uploaded_file.name
            else:
                with st.expander("Preview"):
                    st.text_area("Resume text", st.session_state.resume_text[:500] + "...", height=150, disabled=True)
    
    # Show recently uploaded PDFs
    st.divider()
    st.subheader("📚 Recent PDFs")
    try:
        recent_pdfs = get_uploaded_pdfs()
        if recent_pdfs:
            for pdf_info in recent_pdfs[:5]:  # Show last 5
                col1, col2, col3 = st.columns([3, 1, 1])
                with col1:
                    st.write(f"📄 {pdf_info['name']}")
                    st.caption(f"Modified: {pdf_info['modified']}")
                with col2:
                    if st.button("👁️ View", key=f"view_{pdf_info['name']}"):
                        try:
                            pdf_bytes = load_pdf_bytes(pdf_info['path'])
                            st.session_state.show_pdf_modal = True
                            st.session_state.pdf_modal_bytes = pdf_bytes
                            st.session_state.pdf_modal_name = pdf_info['name']
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error loading PDF: {str(e)}")
                with col3:
                    if st.button("🗑️", key=f"del_{pdf_info['name']}"):
                        try:
                            delete_pdf(pdf_info['path'])
                            st.success("Deleted")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error deleting: {str(e)}")
        else:
            st.info("No PDFs uploaded yet")
    except Exception as e:
        st.warning(f"Could not load recent PDFs: {str(e)}")
    
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
                st.markdown(f"""
                <div style="
                    background:#111318;
                    border:1px solid #1e2130;
                    border-radius:14px;
                    padding:1.2rem 1.4rem 0.4rem;
                    margin-bottom:0.8rem;
                ">
                    <span style="font-size:0.7rem;font-weight:600;letter-spacing:0.1em;color:#5a6180;text-transform:uppercase;">
                        Goal {i+1}
                    </span>
                </div>
                """, unsafe_allow_html=True)
                col1, col2 = st.columns([2, 1])
                with col1:
                    label = st.text_input(f"Label", placeholder="e.g. Senior ML Engineer", key=f"goal_label_{i}")
                with col2:
                    confidence = st.select_slider(f"Confidence", ["low", "medium", "high"], "high", key=f"goal_conf_{i}")
                desc = st.text_area(f"Description", placeholder="Describe what this goal means for your career...", height=60, key=f"goal_desc_{i}")
                
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
            active_badge = '<span style="background:rgba(99,102,241,0.15);color:#a5b4fc;font-size:0.7rem;font-weight:600;padding:3px 10px;border-radius:20px;border:1px solid rgba(99,102,241,0.3);">● Active</span>' if goal_set.is_active else ''
            st.markdown(f"""
            <div style="background:#111318;border:1px solid #1e2130;border-radius:12px;padding:1rem 1.2rem;margin-bottom:0.6rem;display:flex;align-items:center;justify-content:space-between;">
                <div>
                    <span style="color:#e0e4f0;font-weight:600;font-size:0.9rem;">{goal_set.name}</span>
                    <span style="color:#5a6180;font-size:0.78rem;margin-left:10px;">{len(goal_set.goals)} goals</span>
                </div>
                {active_badge}
            </div>
            """, unsafe_allow_html=True)
            col1, col2 = st.columns([5, 1])
            with col2:
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