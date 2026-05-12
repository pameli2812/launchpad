"""Main Streamlit app - Launchpad Resume AI Analyzer."""

import streamlit as st
import hashlib
from typing import Optional

from utils.models import GoalSet
from pages.setup.setup import render_setup_tab
from pages.analyse.analyse import render_analyse_tab
from pages.history.history import render_history_tab
from pages.common import render_pdf_modal


# ═══════════════════════════════════════════════════════════════
# PAGE CONFIG & SESSION STATE INIT
# ═══════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="Launchpad — Your AI-powered career co-pilot",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize session state
if "resume_text" not in st.session_state:
    st.session_state.resume_text = None
if "resume_filename" not in st.session_state:
    st.session_state.resume_filename = None
if "resume_pdf_bytes" not in st.session_state:
    st.session_state.resume_pdf_bytes = None
if "last_uploaded_file" not in st.session_state:
    st.session_state.last_uploaded_file = None

if "goal_sets" not in st.session_state:
    st.session_state.goal_sets = {}
if "active_goal_set_id" not in st.session_state:
    st.session_state.active_goal_set_id = None

if "current_analysis" not in st.session_state:
    st.session_state.current_analysis = None
if "suggestions" not in st.session_state:
    st.session_state.suggestions = None

if "history" not in st.session_state:
    st.session_state.history = []

if "show_pdf_modal" not in st.session_state:
    st.session_state.show_pdf_modal = False
if "pdf_modal_bytes" not in st.session_state:
    st.session_state.pdf_modal_bytes = None
if "pdf_modal_name" not in st.session_state:
    st.session_state.pdf_modal_name = None

if "force_suggestions" not in st.session_state:
    st.session_state.force_suggestions = False
if "auto_inferred_goals" not in st.session_state:
    st.session_state.auto_inferred_goals = []


def get_resume_hash(text: str) -> str:
    """Generate short hash of resume text for change detection."""
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def get_active_goal_set() -> Optional[GoalSet]:
    """Get the currently active goal set."""
    if not st.session_state.active_goal_set_id:
        return None
    return st.session_state.goal_sets.get(st.session_state.active_goal_set_id)


# ═══════════════════════════════════════════════════════════════
# TOP BAR
# ═══════════════════════════════════════════════════════════════

col1, col2, col3 = st.columns([2, 4, 2])
with col1:
    st.title("🚀 Launchpad")
with col2:
    if st.session_state.resume_text:
        st.success(f"✓ Resume: {st.session_state.resume_filename}")
    else:
        st.info("No resume loaded yet")
with col3:
    pass


# ═══════════════════════════════════════════════════════════════
# PDF MODAL (must be called before tabs)
# ═══════════════════════════════════════════════════════════════

render_pdf_modal()


# ═══════════════════════════════════════════════════════════════
# MAIN TABS
# ═══════════════════════════════════════════════════════════════

tab1, tab2, tab3 = st.tabs(["Setup", "Analyze", "History"])

with tab1:
    render_setup_tab()

with tab2:
    render_analyse_tab()

with tab3:
    render_history_tab()