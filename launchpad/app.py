"""Main Streamlit app - Launchpad Your AI-powered career co-pilot."""

import streamlit as st
import hashlib
from typing import Optional

from utils.models import GoalSet
from pages.setup.setup import render_setup_tab
from pages.analyse.analyse import render_analyse_tab
from pages.history.history import render_history_tab
from pages.common import render_pdf_modal


st.set_page_config(
    page_title="Launchpad — Your AI-powered career co-pilot",
    layout="wide",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    /* ── App shell ── */
    html, body,
    [data-testid="stApp"],
    [data-testid="stAppViewContainer"],
    [data-testid="stAppViewBlockContainer"],
    .main, .block-container {
        background-color: #f8f9fb !important;
        color: #1a1a2e !important;
    }
    [data-testid="collapsedControl"],
    section[data-testid="stSidebar"] { display: none !important; }
    header[data-testid="stHeader"] {
        background-color: #ffffff !important;
        border-bottom: 1px solid #e2e8f0 !important;
    }

    /* ── Text ── */
    p, span, div, li, label, h1, h2, h3, h4, h5, h6,
    .stMarkdown, .stText { color: #1a1a2e !important; }
    .stCaption, [data-testid="stCaptionContainer"] * { color: #64748b !important; }

    /* ── Text inputs / textareas ── */
    input, textarea,
    .stTextInput input,
    .stTextArea textarea,
    .stNumberInput input,
    [data-baseweb="input"] input,
    [data-baseweb="textarea"] textarea {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
        caret-color: #1a1a2e !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
    }
    [data-baseweb="input"],
    [data-baseweb="textarea"],
    [data-baseweb="base-input"],
    .stTextInput > div,
    .stTextArea > div {
        background-color: #ffffff !important;
        border-color: #cbd5e1 !important;
    }
    input::placeholder, textarea::placeholder {
        color: #94a3b8 !important; opacity: 1 !important;
    }

    /* ── ALL DROPDOWNS / SELECTS — white background, dark text ── */
    /* Selectbox trigger button */
    .stSelectbox > div > div,
    [data-baseweb="select"] > div,
    [data-baseweb="select"] > div > div {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
    }
    /* Selected value text */
    [data-baseweb="select"] [data-testid="stMarkdownContainer"] p,
    [data-baseweb="select"] span,
    [data-baseweb="select"] div {
        color: #1a1a2e !important;
        background-color: transparent !important;
    }
    /* Dropdown arrow */
    [data-baseweb="select"] svg { fill: #64748b !important; }
    /* Dropdown menu panel */
    [data-baseweb="menu"],
    [data-baseweb="popover"],
    ul[data-baseweb="menu"],
    div[data-baseweb="popover"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
    }
    /* Dropdown menu items */
    [data-baseweb="menu"] li,
    [data-baseweb="menu"] [role="option"],
    [data-baseweb="menu"] div {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
    }
    [data-baseweb="menu"] li:hover,
    [data-baseweb="menu"] [role="option"]:hover {
        background-color: #eff6ff !important;
        color: #2563eb !important;
    }
    /* Selected option in menu */
    [aria-selected="true"] {
        background-color: #dbeafe !important;
        color: #1e40af !important;
    }
    /* Native select element fallback */
    select {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
    }

    /* ── Radio buttons ── */
    .stRadio label, .stRadio div, .stRadio span { color: #1a1a2e !important; }
    [data-baseweb="radio"] div { background-color: transparent !important; }

    /* ── File uploader ── */
    [data-testid="stFileUploader"],
    [data-testid="stFileUploader"] > div,
    [data-testid="stFileUploaderDropzone"] {
        background-color: #ffffff !important;
        border: 1.5px dashed #93c5fd !important;
        border-radius: 8px !important;
        color: #1a1a2e !important;
    }
    [data-testid="stFileUploaderDropzone"] span,
    [data-testid="stFileUploaderDropzone"] p,
    [data-testid="stFileUploaderDropzone"] small { color: #1a1a2e !important; }
    [data-testid="stFileUploaderDropzone"] svg { fill: #2563eb !important; stroke: #2563eb !important; }
    [data-testid="stFileUploaderFile"],
    [data-testid="stFileUploaderFile"] * { background-color: #f1f5f9 !important; color: #1a1a2e !important; }
    [data-testid="stFileUploaderDropzoneInstructions"] button,
    [data-testid="stFileUploaderDropzone"] button,
    [data-testid="stFileUploader"] button {
        background-color: #e8f0fe !important;
        color: #2563eb !important;
        border: 1px solid #93c5fd !important;
        border-radius: 6px !important;
    }

    /* ── Standard buttons ── */
    .stButton > button {
        background-color: #2563eb !important;
        color: #ffffff !important;
        border: none !important;
        border-radius: 6px !important;
        font-weight: 500 !important;
    }
    .stButton > button:hover { background-color: #1d4ed8 !important; color: #ffffff !important; }

    /* ── Active goal button — green ── */
    .stButton > button[data-active-goal="true"],
    button[kind="primary"] { 
        background-color: #16a34a !important;
        color: #ffffff !important;
        border: none !important;
    }

    /* Tooltips — white background, dark text */
    [data-testid="stTooltipHoverTarget"] > div,
    div[role="tooltip"],
    [data-baseweb="tooltip"],
    [data-baseweb="tooltip"] div {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
    }

    .stDownloadButton > button {
        background-color: #0f766e !important; color: #ffffff !important;
        border: none !important; border-radius: 6px !important;
    }

    /* ── Tabs ── */
    [data-testid="stTabs"] [role="tablist"] {
        background: #ffffff !important;
        border-bottom: 1px solid #e2e8f0 !important;
    }
    [data-testid="stTabs"] [role="tab"] {
        color: #64748b !important; font-weight: 500 !important; background: transparent !important;
    }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
        color: #2563eb !important;
        border-bottom: 2px solid #2563eb !important;
        background: #ffffff !important;
    }

    /* ── Metrics ── */
    [data-testid="stMetric"] {
        background: #ffffff !important; border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important; padding: 0.75rem 1rem !important;
    }
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { color: #1a1a2e !important; }

    /* ── Alerts ── */
    [data-testid="stAlert"] { border-radius: 8px !important; color: #1a1a2e !important; }

    /* ── Expander ── */
    [data-testid="stExpander"] {
        background: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 8px !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary * { color: #1a1a2e !important; }

    /* ── Dataframe ── */
    div[data-testid="stDataFrame"] thead tr th {
        background-color: #1e3a5f !important; color: #ffffff !important; font-weight: 600 !important;
    }
    div[data-testid="stDataFrame"] tbody tr td { color: #1a1a2e !important; }

    hr { border-color: #e2e8f0 !important; }
    .main .block-container { padding-top: 2rem !important; max-width: 1100px !important; }

    /* ── Number input ── */
    [data-testid="stNumberInput"] > div { background-color: #ffffff !important; }
    [data-testid="stNumberInput"] input {
        background-color: #ffffff !important; color: #1a1a2e !important; caret-color: #1a1a2e !important;
    }
    [data-testid="stNumberInput"] button {
        background-color: #f1f5f9 !important; color: #1a1a2e !important; border: 1px solid #cbd5e1 !important;
    }
    </style>

    <script>
    /* Make Active goal buttons green + fix tooltip text color */
    (function () {
        function applyStyles() {
            document.querySelectorAll('button').forEach(function(btn) {
                const text = (btn.innerText || btn.textContent || '').trim();
                if (text === 'Active') {
                    btn.style.setProperty('background-color', '#16a34a', 'important');
                    btn.style.setProperty('color', '#ffffff', 'important');
                    btn.style.setProperty('border', '1px solid #16a34a', 'important');
                }
            });
            /* Tooltip text fix */
            document.querySelectorAll('[role="tooltip"], [data-baseweb="tooltip"]').forEach(function(tip) {
                tip.style.setProperty('background-color', '#ffffff', 'important');
                tip.style.setProperty('color', '#1a1a2e', 'important');
                tip.style.setProperty('border', '1px solid #e2e8f0', 'important');
            });
        }
        applyStyles();
        new MutationObserver(function() { setTimeout(applyStyles, 50); })
            .observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    """,
    unsafe_allow_html=True,
)

# ── Session state defaults ─────────────────────────────────────
defaults = {
    "resume_text": None,
    "resume_filename": None,
    "resume_pdf_bytes": None,
    "last_uploaded_file": None,
    "goal_sets": {},
    "active_goal_set_id": None,
    "current_analysis": None,
    "suggestions": None,
    "history": [],
    "show_pdf_modal": False,
    "pdf_modal_bytes": None,
    "pdf_modal_name": None,
    "force_suggestions": False,
    "auto_inferred_goals": [],
    "resume_library": {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def get_active_goal_set() -> Optional[GoalSet]:
    if not st.session_state.active_goal_set_id:
        return None
    return st.session_state.goal_sets.get(st.session_state.active_goal_set_id)


# ── Top bar ────────────────────────────────────────────────────
col1, col2, _ = st.columns([3, 4, 1])
with col1:
    st.markdown(
        "<h2 style='margin-bottom:0; color:#1a1a2e;'>Launchpad</h2>"
        "<p style='margin-top:0; color:#64748b; font-size:0.85rem;'>Your AI-powered career co-pilot</p>",
        unsafe_allow_html=True,
    )
with col2:
    if st.session_state.resume_text:
        st.success(f"Resume: {st.session_state.resume_filename}")
    else:
        st.info("No resume loaded yet")

render_pdf_modal()

# Analyze is the landing tab
tab2, tab1, tab3 = st.tabs(["Analyze", "Setup", "History"])

with tab2:
    render_analyse_tab()
with tab1:
    render_setup_tab()
with tab3:
    render_history_tab()