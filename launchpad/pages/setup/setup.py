# setup.py


"""Setup tab - Resume upload and goal management."""

import streamlit as st
import uuid
from datetime import datetime
from io import BytesIO

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
                {
                    "id": g.id,
                    "label": g.label,
                    "description": g.description,
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
    for gid, gs in st.session_state.goal_sets.items():
        gs.is_active = gid == gs_id
    st.session_state.active_goal_set_id = gs_id
    save_goal_sets(st.session_state.goal_sets, st.session_state.active_goal_set_id)


def _deactivate_goal_set(gs_id: str):
    st.session_state.goal_sets[gs_id].is_active = False
    st.session_state.active_goal_set_id = None
    save_goal_sets(st.session_state.goal_sets, st.session_state.active_goal_set_id)


def _load_resume_library_from_disk():
    """Restore resume library from saved PDFs on disk (for new tab / refresh)."""
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
                st.session_state.resume_library[name] = {
                    "text": text,
                    "pdf_bytes": pdf_bytes,
                }
            except Exception:
                pass

    # Auto-load most recent into active resume slot if nothing loaded
    if st.session_state.resume_library and not st.session_state.get("resume_text"):
        first_name = list(st.session_state.resume_library.keys())[0]
        st.session_state.resume_text = st.session_state.resume_library[first_name]["text"]
        st.session_state.resume_filename = first_name
        st.session_state.resume_pdf_bytes = st.session_state.resume_library[first_name]["pdf_bytes"]


# ─────────────────────────────────────────────
# Main render
# ─────────────────────────────────────────────

def render_setup_tab():

    # ── One-time startup loads ─────────────────────────────────
    if "goal_sets_loaded" not in st.session_state:
        loaded_gs, active_id = load_goal_sets()
        if loaded_gs:
            st.session_state.goal_sets = loaded_gs
            st.session_state.active_goal_set_id = active_id
        st.session_state.goal_sets_loaded = True

    if "resume_library_loaded" not in st.session_state:
        _load_resume_library_from_disk()
        st.session_state.resume_library_loaded = True

    # Style ONLY the active goal button
    st.markdown(
        """
        <script>
        (function () {

            function styleActiveButtons() {

                document.querySelectorAll('button').forEach(function(btn) {

                    const text = (btn.innerText || btn.textContent || '').trim();

                    if (text === '✓ Active') {

                        btn.style.background = '#16a34a';
                        btn.style.border = '1px solid #16a34a';
                        btn.style.color = '#ffffff';
                        btn.style.boxShadow = 'none';

                    }

                });

            }

            styleActiveButtons();

            const observer = new MutationObserver(function() {
                setTimeout(styleActiveButtons, 50);
            });

            observer.observe(document.body, {
                childList: true,
                subtree: true
            });

        })();
        </script>
        """,
        unsafe_allow_html=True,
    )

    # ── Section 1: Upload Resume ───────────────────────────────
    st.header("Step 1: Upload Resume")

    uploaded_file = st.file_uploader(
        "Upload your resume (PDF or DOCX)",
        type=["pdf", "docx"],
        key="resume_uploader",
    )

    # Only process a newly uploaded file — compare by name to avoid re-processing
    if uploaded_file and uploaded_file.name != st.session_state.get("last_uploaded_file"):
        try:
            pdf_bytes = uploaded_file.getvalue()

            if uploaded_file.type == "application/pdf":
                resume_text = extract_text_from_pdf(BytesIO(pdf_bytes))
                try:
                    save_pdf_locally(pdf_bytes, uploaded_file.name)
                except Exception as e:
                    st.warning(f"Could not save PDF locally: {e}")
                st.session_state.resume_pdf_bytes = pdf_bytes
            else:
                resume_text = extract_text_from_docx(uploaded_file)
                pdf_bytes = None
                st.session_state.resume_pdf_bytes = None

            st.session_state.resume_text = resume_text
            st.session_state.resume_filename = uploaded_file.name
            st.session_state.last_uploaded_file = uploaded_file.name

            if "resume_library" not in st.session_state:
                st.session_state.resume_library = {}
            st.session_state.resume_library[uploaded_file.name] = {
                "text": resume_text,
                "pdf_bytes": pdf_bytes,
            }

            # Do NOT auto-open viewer here — user must click the button
            st.success(f"Uploaded: {uploaded_file.name}")

        except Exception as e:
            st.error(f"Error parsing resume: {e}")

    # Show viewer button only when a PDF is loaded and uploader has a file selected
    if (
        uploaded_file
        and uploaded_file.type == "application/pdf"
        and st.session_state.get("resume_pdf_bytes")
        and st.session_state.get("resume_filename") == uploaded_file.name
    ):
        if st.button("Open in Viewer", key="open_pdf_btn"):
            st.session_state.show_pdf_modal = True
            st.session_state.pdf_modal_bytes = st.session_state.resume_pdf_bytes
            st.session_state.pdf_modal_name = st.session_state.resume_filename
            st.rerun()

    # ── Saved Resumes ──────────────────────────────────────────
    st.divider()
    st.subheader("Saved Resumes")

    try:
        recent_pdfs = get_uploaded_pdfs()
        if recent_pdfs:
            for pdf_info in recent_pdfs[:5]:
                col1, col2, col3 = st.columns([4, 1, 1])
                with col1:
                    st.write(pdf_info["name"])
                    st.caption(f"Modified: {pdf_info['modified']}")
                with col2:
                    if st.button("View", key=f"view_{pdf_info['name']}"):
                        pdf_bytes = load_pdf_bytes(pdf_info["path"])
                        st.session_state.show_pdf_modal = True
                        st.session_state.pdf_modal_bytes = pdf_bytes
                        st.session_state.pdf_modal_name = pdf_info["name"]
                        st.rerun()
                with col3:
                    if st.button("Delete", key=f"del_{pdf_info['name']}"):
                        delete_pdf(pdf_info["path"])
                        st.session_state.resume_library.pop(pdf_info["name"], None)
                        st.success("Deleted")
                        st.rerun()
        else:
            st.info("No resumes saved yet.")
    except Exception as e:
        st.warning(str(e))

    # ── Section 2: Career Goals ────────────────────────────────
    st.divider()
    st.header("Step 2: Create a Goal Set")

    if not st.session_state.get("resume_text"):
        st.warning("Upload a resume first before setting goals.")
        return

    col1, col2 = st.columns(2)
    with col1:
        goal_set_name = st.text_input("Goal set name", key="new_gs_name")
    with col2:
        goal_input_mode = st.radio(
            "How to set goals?",
            ["Manual", "Auto-infer from resume"],
            index=0,
            key="goal_input_mode",
        )

    goals = []

    if goal_input_mode == "Auto-infer from resume":
        if st.button("Auto-infer goals", key="autoinfer_btn"):
            with st.spinner("Inferring goals..."):
                inferred = auto_infer_goals_from_resume(st.session_state.resume_text)
                st.session_state.auto_inferred_goals = inferred

        if st.session_state.get("auto_inferred_goals"):
            goals = st.session_state.auto_inferred_goals
            for i, g in enumerate(goals):
                st.caption(f"{i + 1}. {g['label']} — {g.get('description', '')}")

    else:
        num_goals = st.number_input("Number of goals", 1, 7, 1, key="num_goals")
        for i in range(num_goals):
            label = st.text_input(f"Goal {i + 1} label", key=f"goal_label_{i}")
            desc = st.text_area(f"Goal {i + 1} description", key=f"goal_desc_{i}", height=80)
            if label:
                goals.append({
                    "id": f"goal_{i + 1}",
                    "label": label,
                    "description": desc,
                    "confidence": "high",
                    "auto_inferred": False,
                })

    can_create = bool(goals and goal_set_name and goal_set_name.strip())

    if not goal_set_name:
        st.caption("Enter a goal set name to enable creation.")
    if not goals:
        st.caption("Add at least one goal label to enable creation.")

    if can_create:
        if st.button("Create Goal Set", use_container_width=True, key="create_gs_btn"):
            existing_names = [gs.name for gs in st.session_state.goal_sets.values()]
            if goal_set_name.strip() in existing_names:
                st.warning(f'A goal set named "{goal_set_name.strip()}" already exists.')
            else:
                goal_set_id = str(uuid.uuid4())[:8]
                goal_objects = [
                    Goal(
                        id=g["id"],
                        label=g["label"],
                        description=g.get("description", ""),
                        confidence=g.get("confidence", "high"),
                        auto_inferred=g.get("auto_inferred", False),
                    )
                    for g in goals
                ]
                goal_set = GoalSet(
                    id=goal_set_id,
                    name=goal_set_name.strip(),
                    goals=goal_objects,
                    created_at=datetime.now(),
                    is_active=False,
                )
                st.session_state.goal_sets[goal_set_id] = goal_set
                st.session_state.auto_inferred_goals = []
                save_goal_sets(st.session_state.goal_sets, st.session_state.active_goal_set_id)
                st.success(f'Created: "{goal_set_name.strip()}". Activate it below to use it.')
                st.rerun()

    # ── Goal Sets List ─────────────────────────────────────────
    st.divider()
    st.subheader("Your Goal Sets")

    if not st.session_state.goal_sets:
        st.info("No goal sets yet. Create one above.")
        return

    for gs_id, goal_set in list(st.session_state.goal_sets.items()):
        is_active = goal_set.is_active

        col1, col2, col3, col4 = st.columns([4, 1, 1, 1])

        with col1:
            status_text = " — ACTIVE" if is_active else ""
            status_color = "color:#16a34a" if is_active else "color:#64748b"
            st.markdown(
                f"**{goal_set.name}**"
                f"<span style='{status_color}; font-size:0.82rem; font-weight:600;'>{status_text}</span>",
                unsafe_allow_html=True,
            )
            st.caption(
                f"{len(goal_set.goals)} goals: "
                + ", ".join(g.label for g in goal_set.goals[:3])
                + ("..." if len(goal_set.goals) > 3 else "")
            )

        with col2:
            # if is_active:
            #     if st.button("✓ Active", key=f"deact_{gs_id}", use_container_width=True, help="Click to deactivate"):
            #         _deactivate_goal_set(gs_id)
            #         st.rerun()
            # else:
            #     if st.button("Activate", key=f"act_{gs_id}", use_container_width=True):
            #         _activate_goal_set(gs_id)
            #         st.rerun()
            with col2:

                if is_active:

                    if st.button(
                        "✓ Active",
                        key=f"deact_{gs_id}",
                        use_container_width=True,
                        help="Click to deactivate",
                        type="primary",
                    ):
                        _deactivate_goal_set(gs_id)
                        st.rerun()

                else:

                    if st.button(
                        "Activate",
                        key=f"act_{gs_id}",
                        use_container_width=True,
                    ):
                        _activate_goal_set(gs_id)
                        st.rerun()

        with col3:
            with st.expander("Goals"):
                for g in goal_set.goals:
                    st.markdown(f"**{g.label}**")
                    if g.description:
                        st.caption(g.description)

        with col4:
            if st.button("Delete", key=f"delgs_{gs_id}"):
                del st.session_state.goal_sets[gs_id]
                if st.session_state.active_goal_set_id == gs_id:
                    st.session_state.active_goal_set_id = None
                save_goal_sets(st.session_state.goal_sets, st.session_state.active_goal_set_id)
                st.rerun()

        st.divider()

