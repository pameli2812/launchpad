import streamlit as st
from pages.setup.setup import render_setup_tab
from pages.analyse.analyse import render_analyse_tab
from pages.history.history import render_history_tab
from pages.common import render_pdf_modal

st.set_page_config(
    page_title="Launchpad — Your AI-powered career co-pilot",
    layout="wide",
    initial_sidebar_state="expanded"
)

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

col1, col2, col3 = st.columns([2, 4, 2])
with col1:
    st.title("🚀 Launchpad")
    st.caption("Your AI-powered career co-pilot")
with col2:
    if st.session_state.resume_text:
        st.success(f"✓ Resume: {st.session_state.resume_filename}")
    else:
        st.info("No resume loaded yet")
with col3:
    if st.button("📁 Upload", key="resume_button"):
        st.session_state.show_resume_upload = True

render_pdf_modal()

tab1, tab2, tab3 = st.tabs(["Setup", "Analyze", "History"])

with tab1:
    render_setup_tab()

with tab2:
    render_analyse_tab()

with tab3:
    render_history_tab()