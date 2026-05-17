"""Setup tab - Resume upload and goal management."""

import streamlit as st
import uuid
from datetime import datetime

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


# ─────────────────────────────────────────────
# Persistence helpers
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
                {
                    "id": g.id,
                    "label": g.label,
                    "description": g.description,
                    "confidence": g.confidence,
                    "auto_inferred": g.auto_inferred,
                }
                for g in gs.goals
            ],
        })
    write_json(GOAL_SETS_FILE, serialized)


def load_goal_sets():
    data = read_json(
        GOAL_SETS_FILE,
        default={"goal_sets": [], "active_goal_set_id": None},
    )
    goal_sets = {}
    for gs in data.get("goal_sets", []):
        goal_objects = [
            Goal(
                id=g["id"],
                label=g["label"],
                description=g["description"],
                confidence=g.get("confidence", "high"),
                auto_inferred=g.get("auto_inferred", False),
            )
            for g in gs["goals"]
        ]
        goal_set = GoalSet(
            id=gs["id"],
            name=gs["name"],
            goals=goal_objects,
            created_at=datetime.fromisoformat(gs["created_at"]),
            is_active=gs["is_active"],
        )
        goal_sets[gs["id"]] = goal_set
    return goal_sets, data.get("active_goal_set_id")


def _activate_goal_set(gs_id: str):
    """Enforce exactly one active goal set."""
    for gid, gs in st.session_state.goal_sets.items():
        gs.is_active = gid == gs_id
    st.session_state.active_goal_set_id = gs_id
    save_goal_sets(
        st.session_state.goal_sets,
        st.session_state.active_goal_set_id,
    )


def _deactivate_goal_set(gs_id: str):
    """Deactivate a goal set (no active set)."""
    st.session_state.goal_sets[gs_id].is_active = False
    st.session_state.active_goal_set_id = None
    save_goal_sets(
        st.session_state.goal_sets,
        st.session_state.active_goal_set_id,
    )


# ─────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────

def render_setup_tab():
    """Render the Setup tab."""

    # Load goal sets once
    if "goal_sets_loaded" not in st.session_state:
        loaded_goal_sets, active_id = load_goal_sets()
        if loaded_goal_sets:
            st.session_state.goal_sets = loaded_goal_sets
            st.session_state.active_goal_set_id = active_id
        st.session_state.goal_sets_loaded = True

    # ─── Section 1: Upload Resume ────────────────────────────
    st.header("Step 1: Upload Resume")

    uploaded_file = st.file_uploader(
        "Upload your resume (PDF or DOCX)",
        type=["pdf", "docx"],
    )

    if uploaded_file:
        if st.session_state.last_uploaded_file != uploaded_file.name:
            try:
                pdf_bytes = uploaded_file.getvalue()

                if uploaded_file.type == "application/pdf":
                    resume_text = extract_text_from_pdf(uploaded_file)
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

                # Add to resume library
                if "resume_library" not in st.session_state:
                    st.session_state.resume_library = {}
                st.session_state.resume_library[uploaded_file.name] = {
                    "text": resume_text,
                    "pdf_bytes": pdf_bytes if uploaded_file.type == "application/pdf" else None,
                }

                st.success(f"Uploaded: {uploaded_file.name}")

            except Exception as e:
                st.error(f"Error parsing resume: {str(e)}")

        if st.session_state.resume_text:
            if (
                uploaded_file.type == "application/pdf"
                and st.session_state.resume_pdf_bytes
            ):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write("**PDF loaded**")
                with col2:
                    if st.button("Open in Viewer", key="open_pdf_btn"):
                        st.session_state.show_pdf_modal = True
                        st.session_state.pdf_modal_bytes = st.session_state.resume_pdf_bytes
                        st.session_state.pdf_modal_name = uploaded_file.name
            else:
                with st.expander("Preview extracted text"):
                    st.text_area(
                        "Resume text",
                        st.session_state.resume_text[:500] + "...",
                        height=150,
                        disabled=True,
                    )

    # ─── Recent PDFs ─────────────────────────────────────────
    st.divider()
    st.subheader("Saved Resumes")

    try:
        recent_pdfs = get_uploaded_pdfs()
        if recent_pdfs:
            for pdf_info in recent_pdfs[:5]:
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.write(f"{pdf_info['name']}")
                    st.caption(f"Modified: {pdf_info['modified']}")
                with col2:
                    if st.button("View", key=f"view_{pdf_info['name']}"):
                        pdf_bytes = load_pdf_bytes(pdf_info["path"])
                        st.session_state.show_pdf_modal = True
                        st.session_state.pdf_modal_bytes = pdf_bytes
                        st.session_state.pdf_modal_name = pdf_info["name"]
                with col3:
                    if st.button("Delete", key=f"del_{pdf_info['name']}"):
                        delete_pdf(pdf_info["path"])
                        st.success("Deleted")
                        st.rerun()
        else:
            st.info("No resumes saved yet")
    except Exception as e:
        st.warning(str(e))

    # ─── Section 2: Career Goals ─────────────────────────────
    st.divider()
    st.header("Step 2: Create a Goal Set")

    if not st.session_state.resume_text:
        st.warning("Upload a resume first before setting goals.")
        return

    col1, col2 = st.columns(2)
    with col1:
        goal_set_name = st.text_input("Goal set name")
    with col2:
        goal_input_mode = st.radio(
            "How to set goals?",
            ["Manual", "Auto-infer from resume"],
            index=0,
        )

    goals = []

    if goal_input_mode == "Auto-infer from resume":
        if st.button("Auto-infer goals"):
            inferred = auto_infer_goals_from_resume(st.session_state.resume_text)
            st.session_state.auto_inferred_goals = inferred
        if st.session_state.get("auto_inferred_goals"):
            goals = st.session_state.auto_inferred_goals
            for i, g in enumerate(goals):
                st.caption(f"{i + 1}. {g['label']} — {g.get('description', '')}")
    else:
        num_goals = st.number_input("Number of goals", 1, 7, 1)
        for i in range(num_goals):
            col1, col2 = st.columns([3, 1])
            with col1:
                label = st.text_input(f"Goal {i + 1} label", key=f"goal_label_{i}")
            with col2:
                confidence = st.select_slider(
                    "Confidence",
                    ["low", "medium", "high"],
                    value="high",
                    key=f"goal_conf_{i}",
                )
            desc = st.text_area(f"Goal {i + 1} description", key=f"goal_desc_{i}")
            if label:
                goals.append({
                    "id": f"goal_{i + 1}",
                    "label": label,
                    "description": desc,
                    "confidence": confidence,
                    "auto_inferred": False,
                })

    if goals and goal_set_name:
        if st.button("Create Goal Set", use_container_width=True):
            # New set starts inactive — user must explicitly activate it
            goal_set_id = str(uuid.uuid4())[:8]
            goal_objects = [Goal(**g) for g in goals]
            goal_set = GoalSet(
                id=goal_set_id,
                name=goal_set_name,
                goals=goal_objects,
                created_at=datetime.now(),
                is_active=False,
            )
            st.session_state.goal_sets[goal_set_id] = goal_set
            save_goal_sets(
                st.session_state.goal_sets,
                st.session_state.active_goal_set_id,
            )
            st.success(f"Created: {goal_set_name}. Activate it below to use it.")
            st.rerun()
    elif goals and not goal_set_name:
        st.caption("Enter a goal set name to save.")

    # ─── Goal Sets List ───────────────────────────────────────
    st.divider()
    st.subheader("Your Goal Sets")

    if not st.session_state.goal_sets:
        st.info("No goal sets yet. Create one above.")
        return

    active_id = st.session_state.active_goal_set_id

    for gs_id, goal_set in list(st.session_state.goal_sets.items()):
        is_active = goal_set.is_active

        # Card-like container
        with st.container():
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])

            with col1:
                badge = "[ ACTIVE ]" if is_active else ""
                st.markdown(
                    f"**{goal_set.name}** "
                    f"<span style='color:#2563eb; font-size:0.8rem;'>{badge}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"{len(goal_set.goals)} goals — "
                    + ", ".join(g.label for g in goal_set.goals[:3])
                    + ("..." if len(goal_set.goals) > 3 else "")
                )

            with col2:
                if is_active:
                    if st.button("Deactivate", key=f"deact_{gs_id}"):
                        _deactivate_goal_set(gs_id)
                        st.rerun()
                else:
                    if st.button("Activate", key=f"act_{gs_id}"):
                        _activate_goal_set(gs_id)
                        st.rerun()

            with col3:
                with st.expander("Goals"):
                    for g in goal_set.goals:
                        st.markdown(f"**{g.label}** ({g.confidence})")
                        if g.description:
                            st.caption(g.description)

            with col4:
                if st.button("Delete", key=f"delgs_{gs_id}"):
                    del st.session_state.goal_sets[gs_id]
                    if st.session_state.active_goal_set_id == gs_id:
                        st.session_state.active_goal_set_id = None
                    save_goal_sets(
                        st.session_state.goal_sets,
                        st.session_state.active_goal_set_id,
                    )
                    st.rerun()

        st.divider()
