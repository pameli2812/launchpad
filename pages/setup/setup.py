"""Setup tab - Resume upload and goal management."""

import streamlit as st
import uuid
from datetime import datetime
from io import BytesIO
from pathlib import Path

from utils.parser import extract_text_from_pdf, extract_text_from_docx
from utils.goal_inference import auto_infer_goals_from_resume
from utils.pdf_viewer import (
    save_pdf_locally,
    get_uploaded_pdfs,
    load_pdf_bytes,
    delete_pdf,
)
from utils.models import Goal, GoalSet
from utils.storage import write_json, read_json


GOAL_SETS_FILE = "data/goal_sets.json"
MAX_FILE_SIZE_MB = 5


# ─────────────────────────────────────────────
# Persistence
# ─────────────────────────────────────────────

def save_goal_sets(goal_sets, active_goal_set_id):
    serialized = {
        "active_goal_set_id": active_goal_set_id,
        "goal_sets": [],
    }
    for gs_id, gs in goal_sets.items():
        serialized["goal_sets"].append({
            "id": gs.id,
            "name": gs.name,
            "created_at": gs.created_at.isoformat(),
            "is_active": gs.is_active,
            "goals": [
                {"id": g.id, "label": g.label, "description": g.description, "auto_inferred": g.auto_inferred}
                for g in gs.goals
            ],
        })
    write_json(GOAL_SETS_FILE, serialized)


def load_goal_sets():
    data = read_json(GOAL_SETS_FILE, default={"goal_sets": [], "active_goal_set_id": None})
    goal_sets = {}
    for gs in data.get("goal_sets", []):
        goal_objects = [
            Goal(
                id=g["id"], label=g["label"], description=g["description"],
                auto_inferred=g.get("auto_inferred", False)
            )
            for g in gs["goals"]
        ]
        goal_set = GoalSet(
            id=gs["id"], name=gs["name"], goals=goal_objects,
            created_at=datetime.fromisoformat(gs["created_at"]), is_active=gs["is_active"],
        )
        goal_sets[gs["id"]] = goal_set
    return goal_sets, data.get("active_goal_set_id")


def _activate_goal_set(gs_id: str):
    for gid, gs in st.session_state.goal_sets.items():
        gs.is_active = gid == gs_id
    st.session_state.active_goal_set_id = gs_id
    save_goal_sets(st.session_state.goal_sets, st.session_state.active_goal_set_id)


def _deactivate_goal_set(gs_id: str):
    st.session_state.goal_sets[gs_id].is_active = False
    st.session_state.active_goal_set_id = None
    save_goal_sets(st.session_state.goal_sets, st.session_state.active_goal_set_id)


def _load_resume_library_from_disk():
    if "resume_library" not in st.session_state:
        st.session_state.resume_library = {}
    try:
        saved_pdfs = get_uploaded_pdfs()
    except Exception:
        saved_pdfs = []
    for pdf_info in saved_pdfs:
        name = pdf_info["name"]
        if name not in st.session_state.resume_library:
            try:
                pdf_bytes = load_pdf_bytes(pdf_info["path"])
                text = extract_text_from_pdf(BytesIO(pdf_bytes))
                st.session_state.resume_library[name] = {"text": text, "pdf_bytes": pdf_bytes}
            except Exception:
                pass
    if st.session_state.resume_library and not st.session_state.get("resume_text"):
        first_name = list(st.session_state.resume_library.keys())[0]
        st.session_state.resume_text = st.session_state.resume_library[first_name]["text"]
        st.session_state.resume_filename = first_name
        st.session_state.resume_pdf_bytes = st.session_state.resume_library[first_name]["pdf_bytes"]


def _inject_active_btn_style():
    st.markdown(
        """
        <script>
        (function () {
            function styleActive() {
                document.querySelectorAll('button').forEach(function(btn) {
                    const txt = (btn.innerText || btn.textContent || '').trim();
                    if (txt === 'Active') {
                        btn.style.setProperty('background-color', '#16a34a', 'important');
                        btn.style.setProperty('color', '#ffffff', 'important');
                        btn.style.setProperty('border', '1px solid #16a34a', 'important');
                    }
                });
            }
            styleActive();
            new MutationObserver(function() { setTimeout(styleActive, 60); })
                .observe(document.body, { childList: true, subtree: true });
        })();
        </script>
        """,
        unsafe_allow_html=True,
    )


# ─────────────────────────────────────────────
# Goal creation panel (shown in an expander)
# ─────────────────────────────────────────────

def _render_create_goal_panel():
    """
    Create New Goal panel — matches wireframe:
    Goal Name input + method choice (Auto-create / Create Manually)
    Auto-create: resume selector + optional context + Generate button + editable list
    Create Manually: card-style add/remove rows
    """
    goal_set_name = st.text_input("Goal Set Name", key="new_gs_name",
                                   placeholder="e.g. Director of Product at AI Startup")

    st.markdown("**How would you like to create goals?**")
    method = st.radio(
        "Method",
        ["Auto-create (AI)", "Create Manually"],
        index=0,
        key="goal_create_method",
        horizontal=True,
        label_visibility="collapsed",
    )

    goals = []

    # ── AUTO-CREATE ───────────────────────────
    if method == "Auto-create (AI)":
        library = st.session_state.get("resume_library", {})
        resume_names = list(library.keys()) if library else []

        if resume_names:
            default_idx = 0
            cur = st.session_state.get("resume_filename")
            if cur in resume_names:
                default_idx = resume_names.index(cur)
            infer_from = st.selectbox(
                "Resume to infer from",
                resume_names,
                index=default_idx,
                key="infer_resume_select",
            )
            infer_text = library[infer_from]["text"]
        else:
            infer_text = st.session_state.get("resume_text", "")

        user_ctx = st.text_area(
            "Describe what you want (optional)",
            placeholder="e.g. I want GenAI/LLM roles, prefer remote, leadership-focused...",
            height=80,
            key="optional_goal_context",
        )

        if st.button("Generate goals", key="autoinfer_btn"):
            with st.spinner("Analyzing resume..."):
                combined = infer_text
                if user_ctx.strip():
                    combined += "\n\nAdditional preferences:\n" + user_ctx.strip()
                inferred = auto_infer_goals_from_resume(combined)
                # Initialize with unique IDs
                st.session_state.auto_inferred_goals = [
                    {"id": str(uuid.uuid4())[:8], "label": g["label"], "description": g.get("description", "")}
                    for g in inferred
                ]
            st.rerun()

        # Show inferred goals for review
        if st.session_state.get("auto_inferred_goals"):
            st.markdown("**Review & edit — then save:**")
            inferred = st.session_state.auto_inferred_goals
            to_remove_id = None
            
            for i, g in enumerate(inferred):
                c1, c2 = st.columns([5, 1])
                with c1:
                    inferred[i]["label"] = st.text_input(
                        f"Metric {i+1}", value=g["label"], key=f"ai_label_{g['id']}"
                    )
                    inferred[i]["description"] = st.text_input(
                        "Description", value=g.get("description", ""), key=f"ai_desc_{g['id']}"
                    )
                with c2:
                    st.write("")
                    st.write("")
                    if st.button("✕", key=f"rm_ai_{g['id']}"):
                        to_remove_id = g['id']
            
            if to_remove_id is not None:
                st.session_state.auto_inferred_goals = [g for g in st.session_state.auto_inferred_goals if g['id'] != to_remove_id]
                st.rerun()

            # Extra manual metrics on top of inferred
            if "extra_goals" not in st.session_state:
                st.session_state.extra_goals = []
            if st.session_state.extra_goals:
                st.markdown("**Additional metrics:**")
            
            to_remove_extra_id = None
            for eg in st.session_state.extra_goals:
                ec1, ec2 = st.columns([5, 1])
                with ec1:
                    eg["label"] = st.text_input("Label", value=eg["label"], key=f"eg_label_{eg['id']}")
                    eg["description"] = st.text_input("Description", value=eg.get("description", ""), key=f"eg_desc_{eg['id']}")
                with ec2:
                    st.write("")
                    st.write("")
                    if st.button("✕", key=f"rm_eg_{eg['id']}"):
                        to_remove_extra_id = eg['id']
            
            if to_remove_extra_id is not None:
                st.session_state.extra_goals = [g for g in st.session_state.extra_goals if g['id'] != to_remove_extra_id]
                st.rerun()
            
            if st.button("+ Add metric", key="add_extra_goal"):
                st.session_state.extra_goals.append({"id": str(uuid.uuid4())[:8], "label": "", "description": ""})
                st.rerun()

            # Build metrics list
            for g in inferred:
                if g["label"].strip():
                    goals.append({"id": f"goal_ai_{g['id']}", "label": g["label"].strip(),
                                  "description": g.get("description", ""), "auto_inferred": True})
            for eg in st.session_state.get("extra_goals", []):
                if eg["label"].strip():
                    goals.append({"id": f"goal_ex_{eg['id']}", "label": eg["label"].strip(),
                                  "description": eg.get("description", ""), "auto_inferred": False})

    # ── CREATE MANUALLY ───────────────────────
    else:
        if "manual_goals" not in st.session_state:
            st.session_state.manual_goals = [{"id": str(uuid.uuid4())[:8], "label": "", "description": ""}]

        to_remove_manual_id = None
        for mg in st.session_state.manual_goals:
            st.markdown(
                f"<div style='background:#f8f9fb; border:1px solid #e2e8f0; "
                f"border-radius:8px; padding:12px 14px; margin-bottom:8px;'>",
                unsafe_allow_html=True,
            )
            mc1, mc2 = st.columns([5, 1])
            with mc1:
                mg["label"] = st.text_input(
                    f"Goal name", value=mg["label"], key=f"mg_label_{mg['id']}",
                    placeholder="e.g. Senior PM at an AI-first company"
                )
                mg["description"] = st.text_area(
                    "What does success look like?", value=mg.get("description", ""),
                    key=f"mg_desc_{mg['id']}", height=68,
                    placeholder="e.g. Leading 5+ PMs, B2B SaaS, GenAI product focus"
                )
            with mc2:
                st.write("")
                st.write("")
                if len(st.session_state.manual_goals) > 1:
                    if st.button("✕", key=f"rm_mg_{mg['id']}"):
                        to_remove_manual_id = mg['id']
            st.markdown("</div>", unsafe_allow_html=True)

        if to_remove_manual_id is not None:
            st.session_state.manual_goals = [mg for mg in st.session_state.manual_goals if mg['id'] != to_remove_manual_id]
            st.rerun()

        ca, cb = st.columns([1, 1])
        with ca:
            if st.button("+ Add goal", key="add_manual_goal"):
                st.session_state.manual_goals.append({"id": str(uuid.uuid4())[:8], "label": "", "description": ""})
                st.rerun()
        with cb:
            if st.button("Clear all", key="clear_manual_goals"):
                st.session_state.manual_goals = [{"id": str(uuid.uuid4())[:8], "label": "", "description": ""}]
                st.rerun()

        goals = [
            {"id": f"goal_m_{mg['id']}", "label": mg["label"].strip(),
             "description": mg.get("description", ""), "auto_inferred": False}
            for mg in st.session_state.manual_goals
            if mg["label"].strip()
        ]

    # ── Save ──────────────────────────────────
    st.divider()
    can_save = bool(goals and goal_set_name and goal_set_name.strip())
    if not goal_set_name:
        st.caption("Enter a goal set name above.")
    elif not goals:
        st.caption("Add at least one goal with a name.")

    if can_save:
        if st.button("Save Goal Set", use_container_width=True, key="save_gs_btn", type="primary"):
            gs_id = str(uuid.uuid4())[:8]
            goal_objects = [
                Goal(id=g["id"], label=g["label"], description=g.get("description", ""),
                     confidence="high", auto_inferred=g.get("auto_inferred", False))
                for g in goals
            ]
            goal_set = GoalSet(
                id=gs_id, name=goal_set_name.strip(),
                goals=goal_objects, created_at=datetime.now(), is_active=False,
            )
            st.session_state.goal_sets[gs_id] = goal_set
            # Reset form
            st.session_state.auto_inferred_goals = []
            st.session_state.extra_goals = []
            st.session_state.manual_goals = [{"label": "", "description": ""}]
            st.session_state.show_create_goal = False
            save_goal_sets(st.session_state.goal_sets, st.session_state.active_goal_set_id)
            st.success(f'Saved "{goal_set_name.strip()}". Activate it in the list above.')
            st.rerun()


# ─────────────────────────────────────────────
# Existing goals — table view (matches wireframe)
# ─────────────────────────────────────────────

def _render_goal_sets_table():
    goal_sets = st.session_state.goal_sets
    if not goal_sets:
        st.info("No goal sets yet. Click 'Add New Goal' below to create one.")
        return

    # Add custom CSS for goal table buttons
    st.markdown(
        """
        <style>
        .goal-table-btn {
            background-color: #f3f4f6 !important;
            border: 1px solid #000000 !important;
            color: #000000 !important;
            font-weight: 500;
        }
        .goal-table-btn:hover {
            background-color: #e5e7eb !important;
        }
        .goal-active-btn {
            background-color: #dcfce7 !important;
            border: 1px solid #16a34a !important;
            color: #16a34a !important;
            font-weight: 600;
        }
        .goal-active-btn:hover {
            background-color: #c6f6d5 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    # Table header
    st.markdown(
        """
        <div style='display:grid; grid-template-columns:2fr 0.8fr 2fr 1.2fr 1fr 0.8fr 0.8fr;
                    padding:12px 16px; background:#f1f5f9; border:1px solid #000000;
                    border-radius:6px 6px 0 0; font-weight:600; font-size:0.85rem; 
                    color:#1a1a2e; margin-bottom:0;'>
            <div>Goal Name</div>
            <div style='text-align:center;'>Metrics</div>
            <div>Description</div>
            <div style='text-align:center;'>Status</div>
            <div style='text-align:center;'>View</div>
            <div style='text-align:center;'>Delete</div>
            <div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    for gs_id, goal_set in list(goal_sets.items()):
        is_active = goal_set.is_active
        status_label = "Active" if is_active else "Inactive"
        desc_preview = goal_set.goals[0].description[:60] + "..." if goal_set.goals and goal_set.goals[0].description else "—"

        # Row container
        st.markdown(
            f"""
            <div style='display:grid; grid-template-columns:2fr 0.8fr 2fr 1.2fr 1fr 0.8fr 0.8fr;
                        padding:0; background:#ffffff; border:1px solid #000000;
                        border-top:none; align-items:center;'>
            """,
            unsafe_allow_html=True,
        )

        col1, col2, col3, col4, col5, col6, col7 = st.columns([2, 0.8, 2, 1.2, 1, 0.8, 0.8])

        with col1:
            st.markdown(f"**{goal_set.name}**")

        with col2:
            st.markdown(f"<div style='text-align:center;'>{len(goal_set.goals)}</div>", unsafe_allow_html=True)

        with col3:
            st.markdown(f"<div style='color:#475569;'>{desc_preview}</div>", unsafe_allow_html=True)

        with col4:
            status_bg = "#dcfce7" if is_active else "#f1f5f9"
            status_color = "#16a34a" if is_active else "#64748b"
            st.markdown(
                f"""
                <div style='text-align:center;'>
                    <span style='background:{status_bg}; color:{status_color};
                                 padding:4px 10px; border-radius:12px; font-size:0.78rem; font-weight:600;'>
                        {status_label}
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

        with col5:
            if st.button("👁️", key=f"view_goals_{gs_id}", help="View goals",
                         use_container_width=True):
                st.session_state.show_goals_expanded = gs_id
                st.rerun()

        with col6:
            if st.button("🗑️", key=f"del_gs_{gs_id}", help="Delete goal set",
                         use_container_width=True):
                del st.session_state.goal_sets[gs_id]
                if st.session_state.active_goal_set_id == gs_id:
                    st.session_state.active_goal_set_id = None
                save_goal_sets(st.session_state.goal_sets, st.session_state.active_goal_set_id)
                st.rerun()

        with col7:
            if is_active:
                if st.button("✓ Active", key=f"deact_{gs_id}", use_container_width=True,
                             help="Click to deactivate"):
                    _deactivate_goal_set(gs_id)
                    st.rerun()
            else:
                if st.button("⊕ Activate", key=f"act_{gs_id}", use_container_width=True,
                             help="Activate this goal set"):
                    _activate_goal_set(gs_id)
                    st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)

        # Show goals if expanded
        if st.session_state.get("show_goals_expanded") == gs_id:
            st.markdown(
                """
                <div style='background:#f8f9fb; border:1px solid #e2e8f0; border-radius:6px; 
                            padding:12px; margin:8px 0;'>
                <strong style='color:#1a1a2e;'>Goals in this set:</strong>
                """,
                unsafe_allow_html=True,
            )
            for g in goal_set.goals:
                st.markdown(f"• **{g.label}**")
                if g.description:
                    st.caption(g.description)
            st.markdown("</div>", unsafe_allow_html=True)


# ─────────────────────────────────────────────
# Resume row card
# ─────────────────────────────────────────────

def _resume_row(pdf_info, is_current, index):
    name = pdf_info["name"]
    size_kb = round(pdf_info["size"] / 1024, 1)
    modified = pdf_info["modified"]
    
    # Create table row with borders
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    
    with col1:
        st.markdown(f"**{name}**")
        st.caption(f"{size_kb} KB • {modified}")
    
    with col2:
        pass
    
    with col3:
        if st.button("👁️ View", key=f"view_{name}_{pdf_info['path']}", 
                     help="View resume",
                     use_container_width=True):
            pdf_bytes = load_pdf_bytes(pdf_info["path"])
            st.session_state.show_pdf_modal = True
            st.session_state.pdf_modal_bytes = pdf_bytes
            st.session_state.pdf_modal_name = name
            st.rerun()
    
    with col4:
        if st.button("🗑️ Delete", key=f"delr_{name}_{pdf_info['path']}", 
                     help="Delete resume",
                     use_container_width=True):
            delete_pdf(pdf_info["path"])
            st.session_state.resume_library.pop(name, None)
            st.rerun()


# ─────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────

def render_setup_tab():

    if "goal_sets_loaded" not in st.session_state:
        loaded_gs, active_id = load_goal_sets()
        if loaded_gs:
            st.session_state.goal_sets = loaded_gs
            st.session_state.active_goal_set_id = active_id
        st.session_state.goal_sets_loaded = True

    if "resume_library_loaded" not in st.session_state:
        _load_resume_library_from_disk()
        st.session_state.resume_library_loaded = True

    if "show_create_goal" not in st.session_state:
        st.session_state.show_create_goal = False

    _inject_active_btn_style()

    # ════════════════════════════════════════
    # SECTION 1 — RESUMES
    # ════════════════════════════════════════
    st.header("Step 1: Resumes")

    uploaded_file = st.file_uploader(
        "Upload resume (PDF or DOCX, max 5 MB)",
        type=["pdf", "docx"],
        key="resume_uploader",
    )

    if uploaded_file:
        file_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_mb > MAX_FILE_SIZE_MB:
            st.error(f"File is {file_mb:.1f} MB — limit is {MAX_FILE_SIZE_MB} MB.")
        elif uploaded_file.name != st.session_state.get("last_uploaded_file"):
            try:
                pdf_bytes = uploaded_file.getvalue()
                if uploaded_file.type == "application/pdf":
                    resume_text = extract_text_from_pdf(BytesIO(pdf_bytes))
                    try:
                        save_pdf_locally(pdf_bytes, uploaded_file.name)
                    except Exception as e:
                        st.warning(f"Could not save PDF: {e}")
                    st.session_state.resume_pdf_bytes = pdf_bytes
                else:
                    resume_text = extract_text_from_docx(uploaded_file)
                    pdf_bytes = None
                    st.session_state.resume_pdf_bytes = None

                original_name = Path(uploaded_file.name).stem
                st.session_state.resume_text = resume_text
                st.session_state.resume_filename = original_name
                st.session_state.last_uploaded_file = uploaded_file.name
                if "resume_library" not in st.session_state:
                    st.session_state.resume_library = {}
                st.session_state.resume_library[original_name] = {"text": resume_text, "pdf_bytes": pdf_bytes}
                st.success(f"Uploaded: {original_name}")
            except Exception as e:
                st.error(f"Error parsing resume: {e}")

        if (
            uploaded_file.type == "application/pdf"
            and st.session_state.get("resume_pdf_bytes")
            and st.session_state.get("resume_filename") == Path(uploaded_file.name).stem
        ):
            if st.button("Open in Viewer", key="open_pdf_btn"):
                st.session_state.show_pdf_modal = True
                st.session_state.pdf_modal_bytes = st.session_state.resume_pdf_bytes
                st.session_state.pdf_modal_name = st.session_state.resume_filename
                st.rerun()

    st.divider()
    st.subheader("Your Resumes")

    # Add custom CSS for button styling
    st.markdown(
        """
        <style>
        .resume-table-btn {
            background-color: #f3f4f6 !important;
            border: 1px solid #000000 !important;
            color: #000000 !important;
            font-weight: 500;
        }
        .resume-table-btn:hover {
            background-color: #e5e7eb !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    try:
        all_pdfs = get_uploaded_pdfs()
    except Exception:
        all_pdfs = []

    if all_pdfs:
        PAGE_SIZE = 5
        total = len(all_pdfs)
        total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
        if "resume_page" not in st.session_state:
            st.session_state.resume_page = 0
        page = st.session_state.resume_page
        current_name = st.session_state.get("resume_filename", "")
        
        # Table header
        st.markdown(
            """
            <div style='display:grid; grid-template-columns:3fr 1fr 1fr 1fr;
                        padding:12px 16px; background:#f1f5f9; border:1px solid #000000;
                        border-radius:6px 6px 0 0; font-weight:600; font-size:0.85rem; 
                        color:#1a1a2e; margin-bottom:0;'>
                <div>File Name</div>
                <div style='text-align:center;'></div>
                <div style='text-align:center;'>View</div>
                <div style='text-align:center;'>Delete</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        
        # Table rows
        for i, pdf_info in enumerate(all_pdfs[page * PAGE_SIZE: (page + 1) * PAGE_SIZE]):
            # Add border styling for each row
            st.markdown(
                f"""
                <div style='display:grid; grid-template-columns:3fr 1fr 1fr 1fr;
                            padding:0; background:#ffffff; border:1px solid #000000;
                            border-top:none; align-items:center;'>
                """,
                unsafe_allow_html=True,
            )
            
            _resume_row(pdf_info, pdf_info["name"] == current_name, i)
            st.markdown("</div>", unsafe_allow_html=True)
        
        if total_pages > 1:
            st.markdown("<div style='height:6px'/>", unsafe_allow_html=True)
            pc1, pc2, pc3 = st.columns([1, 3, 1])
            with pc1:
                if page > 0 and st.button("Previous", key="pg_prev"):
                    st.session_state.resume_page -= 1
                    st.rerun()
            with pc2:
                st.caption(f"Page {page + 1} of {total_pages}  ·  {total} resumes")
            with pc3:
                if page < total_pages - 1 and st.button("Next", key="pg_next"):
                    st.session_state.resume_page += 1
                    st.rerun()
    else:
        st.info("No resumes uploaded yet.")

    # ════════════════════════════════════════
    # SECTION 2 — GOAL SETS
    # ════════════════════════════════════════
    st.divider()
    st.header("Step 2: Goals")

    # Existing goals table — always shown first
    _render_goal_sets_table()

    st.markdown("<div style='height:12px'/>", unsafe_allow_html=True)

    # "Add New Goal" button — toggles the creation panel
    if not st.session_state.show_create_goal:
        if st.button("+ Add New Goal", key="show_create_btn", use_container_width=False):
            if not st.session_state.get("resume_text"):
                st.warning("Upload a resume first.")
            else:
                st.session_state.show_create_goal = True
                # Reset any stale form state when opening
                st.session_state.auto_inferred_goals = []
                st.session_state.extra_goals = []
                st.session_state.manual_goals = [{"label": "", "description": ""}]
                st.rerun()
    else:
        # Creation panel — bordered container to visually match wireframe dialog
        st.markdown(
            """
            <div style='border:1px solid #bfdbfe; border-radius:10px; padding:20px 20px 0 20px;
                        background:#f8faff; margin-bottom:8px;'>
            """,
            unsafe_allow_html=True,
        )

        hc1, hc2 = st.columns([5, 1])
        with hc1:
            st.subheader("Create New Goal Set")
        with hc2:
            if st.button("✕ Close", key="close_create_btn"):
                st.session_state.show_create_goal = False
                st.session_state.auto_inferred_goals = []
                st.rerun()

        _render_create_goal_panel()

        st.markdown("</div>", unsafe_allow_html=True)