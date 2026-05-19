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

# NOTE: The definitive fix for dropdown portals is .streamlit/config.toml (base="light").
# The CSS below handles edge cases and any remaining overrides.
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

    /* ── Inputs ── */
    input, textarea,
    .stTextInput input, .stTextArea textarea, .stNumberInput input,
    [data-baseweb="input"] input, [data-baseweb="textarea"] textarea {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
        caret-color: #1a1a2e !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
    }
    [data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="base-input"],
    .stTextInput > div, .stTextArea > div {
        background-color: #ffffff !important; border-color: #cbd5e1 !important;
    }
    input::placeholder, textarea::placeholder { color: #94a3b8 !important; opacity:1 !important; }

    /* ── Dropdowns — every layer ── */
    /* Trigger box */
    .stSelectbox > div > div,
    [data-baseweb="select"],
    [data-baseweb="select"] > div,
    [data-baseweb="select"] > div > div,
    [data-baseweb="select"] > div > div > div {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
        border: 1px solid #cbd5e1 !important;
        border-radius: 6px !important;
    }
    /* Value text */
    [data-baseweb="select"] span,
    [data-baseweb="select"] [data-testid="stMarkdownContainer"] p {
        color: #1a1a2e !important;
        background: transparent !important;
    }
    /* Arrow */
    [data-baseweb="select"] svg { fill: #64748b !important; }

    /* Portal dropdown panel — rendered outside stApp, needs :root-level vars */
    [data-baseweb="popover"],
    [data-baseweb="popover"] > div,
    [data-baseweb="menu"],
    ul[data-baseweb="menu"] {
        background-color: #ffffff !important;
        border: 1px solid #e2e8f0 !important;
        border-radius: 6px !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.08) !important;
    }
    /* Menu items */
    [data-baseweb="menu"] li,
    [data-baseweb="menu"] [role="option"],
    [data-baseweb="menu"] [role="option"] > div {
        background-color: #ffffff !important;
        color: #1a1a2e !important;
    }
    [data-baseweb="menu"] li:hover,
    [data-baseweb="menu"] [role="option"]:hover,
    [data-baseweb="menu"] [role="option"]:hover > div {
        background-color: #eff6ff !important;
        color: #2563eb !important;
    }
    [data-baseweb="menu"] [aria-selected="true"],
    [data-baseweb="menu"] [aria-selected="true"] > div {
        background-color: #dbeafe !important;
        color: #1e40af !important;
    }
    /* Streamlit internal CSS variable override for portals */
    :root {
        --background-color: #ffffff;
        --secondary-background-color: #f8f9fb;
        --text-color: #1a1a2e;
    }

    /* ── Radio ── */
    .stRadio label, .stRadio div, .stRadio span { color: #1a1a2e !important; }

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
    [data-testid="stFileUploaderDropzone"] svg { fill: #2563eb !important; }
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

    /* ── Buttons ── */
    .stButton > button {
        background-color: #2563eb !important; color: #ffffff !important;
        border: none !important; border-radius: 6px !important; font-weight: 500 !important;
    }
    .stButton > button:hover { background-color: #1d4ed8 !important; }
    .stDownloadButton > button {
        background-color: #0f766e !important; color: #ffffff !important;
        border: none !important; border-radius: 6px !important;
    }

    /* ── Tabs ── */
    [data-testid="stTabs"] [role="tablist"] {
        background: #ffffff !important; border-bottom: 1px solid #e2e8f0 !important;
    }
    [data-testid="stTabs"] [role="tab"] { color: #64748b !important; font-weight:500 !important; }
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
        color: #2563eb !important; border-bottom: 2px solid #2563eb !important; background: #ffffff !important;
    }

    /* ── Metrics ── */
    [data-testid="stMetric"] {
        background: #ffffff !important; border: 1px solid #e2e8f0 !important;
        border-radius: 8px !important; padding: 0.75rem 1rem !important;
    }
    [data-testid="stMetricValue"], [data-testid="stMetricLabel"] { color: #1a1a2e !important; }

    /* ── Misc ── */
    [data-testid="stAlert"] { border-radius: 8px !important; color: #1a1a2e !important; }
    [data-testid="stExpander"] {
        background: #ffffff !important; border: 1px solid #e2e8f0 !important; border-radius: 8px !important;
    }
    [data-testid="stExpander"] summary,
    [data-testid="stExpander"] summary * { color: #1a1a2e !important; }
    div[data-testid="stDataFrame"] thead tr th {
        background-color: #1e3a5f !important; color: #ffffff !important; font-weight: 600 !important;
    }
    div[data-testid="stDataFrame"] tbody tr td { color: #1a1a2e !important; }
    hr { border-color: #e2e8f0 !important; }
    .main .block-container { padding-top: 2rem !important; max-width: 1100px !important; }
    [data-testid="stNumberInput"] > div { background-color: #ffffff !important; }
    [data-testid="stNumberInput"] input { background-color: #ffffff !important; color: #1a1a2e !important; }
    [data-testid="stNumberInput"] button {
        background-color: #f1f5f9 !important; color: #1a1a2e !important; border: 1px solid #cbd5e1 !important;
    }

    /* ── Tooltip ── */
    [role="tooltip"], [data-baseweb="tooltip"], [data-baseweb="tooltip"] div {
        background-color: #ffffff !important; color: #1a1a2e !important;
        border: 1px solid #e2e8f0 !important; border-radius: 6px !important;
    }
    </style>

    <script>
    /* Style resume table buttons and goal table buttons */
    (function () {
        function styleTableButtons() {
            const buttons = document.querySelectorAll('button');
            buttons.forEach(btn => {
                const text = btn.textContent || btn.innerText || '';
                const ariaLabel = btn.getAttribute('aria-label') || '';
                
                // Resume table: View and Delete with icons
                if ((text.includes('👁️') || text.includes('🗑️')) && text.length < 5) {
                    btn.style.setProperty('background-color', '#f3f4f6', 'important');
                    btn.style.setProperty('color', '#000000', 'important');
                    btn.style.setProperty('border', '1px solid #000000', 'important');
                    btn.style.setProperty('font-weight', '500', 'important');
                }
                
                // Goal table: View and Delete icons, smaller
                if ((text.trim() === '👁️' || text.trim() === '🗑️')) {
                    btn.style.setProperty('background-color', '#f3f4f6', 'important');
                    btn.style.setProperty('color', '#000000', 'important');
                    btn.style.setProperty('border', '1px solid #000000', 'important');
                    btn.style.setProperty('font-weight', '600', 'important');
                    btn.style.setProperty('padding', '6px 12px', 'important');
                }
                
                // Activate/Active buttons - green styling
                if (text.includes('Activate') || text.includes('Active')) {
                    btn.style.setProperty('background-color', '#dcfce7', 'important');
                    btn.style.setProperty('color', '#16a34a', 'important');
                    btn.style.setProperty('border', '1px solid #16a34a', 'important');
                    btn.style.setProperty('font-weight', '600', 'important');
                }
            });
        }
        styleTableButtons();
        new MutationObserver(() => setTimeout(styleTableButtons, 60))
            .observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    

    <script>
    /* Active button = green; tooltip text = dark */
    (function () {
        function apply() {
            document.querySelectorAll('button').forEach(function(b) {
                if ((b.innerText || b.textContent || '').trim() === 'Active') {
                    b.style.setProperty('background-color', '#16a34a', 'important');
                    b.style.setProperty('color', '#ffffff', 'important');
                    b.style.setProperty('border', '1px solid #16a34a', 'important');
                }
            });
            document.querySelectorAll('[role="tooltip"],[data-baseweb="tooltip"]').forEach(function(t) {
                t.style.setProperty('background-color', '#ffffff', 'important');
                t.style.setProperty('color', '#1a1a2e', 'important');
            });
        }
        apply();
        new MutationObserver(function() { setTimeout(apply, 50); })
            .observe(document.body, { childList: true, subtree: true });
    })();
    </script>
    """,
    unsafe_allow_html=True,
)

# ── Session state defaults ──────────────────
defaults = {
    "resume_text": None, "resume_filename": None, "resume_pdf_bytes": None,
    "last_uploaded_file": None, "goal_sets": {}, "active_goal_set_id": None,
    "current_analysis": None, "suggestions": None, "history": [],
    "show_pdf_modal": False, "pdf_modal_bytes": None, "pdf_modal_name": None,
    "force_suggestions": False, "auto_inferred_goals": [], "resume_library": {},
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v


def get_active_goal_set() -> Optional[GoalSet]:
    if not st.session_state.active_goal_set_id:
        return None
    return st.session_state.goal_sets.get(st.session_state.active_goal_set_id)


# ── Top bar ────────────────────────────────
col1, col2, _ = st.columns([3, 4, 1])
with col1:
    st.markdown(
        "<h2 style='margin-bottom:0;color:#1a1a2e;'>Launchpad</h2>"
        "<p style='margin-top:0;color:#64748b;font-size:0.85rem;'>Your AI-powered career co-pilot</p>",
        unsafe_allow_html=True,
    )


render_pdf_modal()

tab2, tab1, tab3 = st.tabs(["Analyze", "Setup", "History"])
with tab2:
    render_analyse_tab()
with tab1:
    render_setup_tab()
with tab3:
    render_history_tab()