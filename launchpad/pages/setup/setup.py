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
            Goal(id=g["id"], label=g["label"], description=g["description"], auto_inferred=g.get("auto_inferred", False))
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


# ─────────────────────────────────────────────
# Green active-button JS injection
# ─────────────────────────────────────────────

def _inject_active_btn_style():
    st.markdown(
        """
        <script>
        (function () {
            function styleActive() {
                document.querySelectorAll('button').forEach(function(btn) {
                    if ((btn.innerText || '').trim() === 'Active') {
                        btn.style.background = '#16a34a';
                        btn.style.border = '1px solid #16a34a';
                        btn.style.color = '#ffffff';
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

    _inject_active_btn_style()

    # ════════════════════════════════════════
    # SECTION 1 — RESUME INVENTORY (top)
    # ════════════════════════════════════════
    st.header("Step 1: Resumes")

    # ── Upload ────────────────────────────────
    uploaded_file = st.file_uploader(
        "Upload resume (PDF or DOCX, max 5 MB)",
        type=["pdf", "docx"],
        key="resume_uploader",
    )

    if uploaded_file:
        file_mb = len(uploaded_file.getvalue()) / (1024 * 1024)
        if file_mb > MAX_FILE_SIZE_MB:
            st.error(f"File is {file_mb:.1f} MB — limit is {MAX_FILE_SIZE_MB} MB. Please compress or trim it.")
        elif uploaded_file.name != st.session_state.get("last_uploaded_file"):
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
                # Retain original filename — duplicates are allowed (different versions)
                st.session_state.resume_library[uploaded_file.name] = {
                    "text": resume_text,
                    "pdf_bytes": pdf_bytes,
                }
                st.success(f"Uploaded: {uploaded_file.name}")
            except Exception as e:
                st.error(f"Error parsing resume: {e}")

        # View button — only after upload, single click
        if (
            uploaded_file.type == "application/pdf"
            and st.session_state.get("resume_pdf_bytes")
            and st.session_state.get("resume_filename") == uploaded_file.name
        ):
            if st.button("Open in Viewer", key="open_pdf_btn"):
                st.session_state.show_pdf_modal = True
                st.session_state.pdf_modal_bytes = st.session_state.resume_pdf_bytes
                st.session_state.pdf_modal_name = st.session_state.resume_filename
                st.rerun()

    # ── Resume inventory with pagination ──────
    st.divider()
    st.subheader("Your Resumes")

    try:
        all_pdfs = get_uploaded_pdfs()
    except Exception:
        all_pdfs = []

    if all_pdfs:
        PAGE_SIZE = 5
        total_pages = max(1, (len(all_pdfs) + PAGE_SIZE - 1) // PAGE_SIZE)
        page_key = "resume_page"
        if page_key not in st.session_state:
            st.session_state[page_key] = 0

        page = st.session_state[page_key]
        page_pdfs = all_pdfs[page * PAGE_SIZE : (page + 1) * PAGE_SIZE]

        for pdf_info in page_pdfs:
            col1, col2, col3 = st.columns([5, 1, 1])
            with col1:
                # Show original filename, click to set as active
                is_current = st.session_state.get("resume_filename") == pdf_info["name"]
                label = f"**{pdf_info['name']}**" + (" — current" if is_current else "")
                if st.button(label, key=f"sel_{pdf_info['name']}", use_container_width=True):
                    try:
                        pdf_bytes = load_pdf_bytes(pdf_info["path"])
                        text = extract_text_from_pdf(BytesIO(pdf_bytes))
                        st.session_state.resume_library[pdf_info["name"]] = {"text": text, "pdf_bytes": pdf_bytes}
                        st.session_state.resume_text = text
                        st.session_state.resume_filename = pdf_info["name"]
                        st.session_state.resume_pdf_bytes = pdf_bytes
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
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
                    st.rerun()

        # Pagination controls
        if total_pages > 1:
            pcol1, pcol2, pcol3 = st.columns([1, 2, 1])
            with pcol1:
                if page > 0 and st.button("Previous", key="pg_prev"):
                    st.session_state[page_key] -= 1
                    st.rerun()
            with pcol2:
                st.caption(f"Page {page + 1} of {total_pages}  ({len(all_pdfs)} resumes total)")
            with pcol3:
                if page < total_pages - 1 and st.button("Next", key="pg_next"):
                    st.session_state[page_key] += 1
                    st.rerun()
    else:
        st.info("No resumes uploaded yet.")

    # ════════════════════════════════════════
    # SECTION 2 — GOAL SETS (existing list FIRST)
    # ════════════════════════════════════════
    st.divider()
    st.header("Step 2: Goal Sets")

    # ── Existing goal sets at top ─────────────
    if st.session_state.goal_sets:
        st.subheader("Your Goal Sets")
        for gs_id, goal_set in list(st.session_state.goal_sets.items()):
            is_active = goal_set.is_active
            col1, col2, col3, col4 = st.columns([4, 1, 1, 1])

            with col1:
                status_color = "#16a34a" if is_active else "#64748b"
                status_text = " — ACTIVE" if is_active else ""
                st.markdown(
                    f"**{goal_set.name}**"
                    f"<span style='color:{status_color}; font-size:0.82rem; font-weight:600;'>{status_text}</span>",
                    unsafe_allow_html=True,
                )
                st.caption(
                    f"{len(goal_set.goals)} goals: "
                    + ", ".join(g.label for g in goal_set.goals[:3])
                    + ("..." if len(goal_set.goals) > 3 else "")
                )

            with col2:
                if is_active:
                    if st.button("Active", key=f"deact_{gs_id}", use_container_width=True, help="Click to deactivate"):
                        _deactivate_goal_set(gs_id)
                        st.rerun()
                else:
                    if st.button("Activate", key=f"act_{gs_id}", use_container_width=True):
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
    else:
        st.info("No goal sets yet. Create one below.")

    # ── Create new goal set (below existing list) ─────────────
    st.subheader("Create New Goal Set")

    if not st.session_state.get("resume_text"):
        st.warning("Upload a resume first before creating goals.")
        return

    goal_set_name = st.text_input("Goal set name", key="new_gs_name")

    goal_input_mode = st.radio(
        "How would you like to define goals?",
        ["Manual", "Auto-infer from resume", "Describe what you want (AI generates)"],
        index=0,
        key="goal_input_mode",
        horizontal=True,
    )

    goals = []

    # ── AUTO-INFER ────────────────────────────
    if goal_input_mode == "Auto-infer from resume":
        # Let user pick which resume to infer from
        library = st.session_state.get("resume_library", {})
        resume_names = list(library.keys()) if library else []

        if resume_names:
            default_idx = 0
            cur = st.session_state.get("resume_filename")
            if cur in resume_names:
                default_idx = resume_names.index(cur)
            infer_from = st.selectbox(
                "Resume to infer goals from",
                resume_names,
                index=default_idx,
                key="infer_resume_select",
            )
            infer_text = library[infer_from]["text"]
        else:
            infer_from = None
            infer_text = st.session_state.get("resume_text", "")

        if st.button("Generate goals from resume", key="autoinfer_btn"):
            with st.spinner("Analyzing resume for goals..."):
                inferred = auto_infer_goals_from_resume(infer_text)
                st.session_state.auto_inferred_goals = inferred
                st.session_state.auto_inferred_edits = {
                    i: {"label": g["label"], "description": g.get("description", "")}
                    for i, g in enumerate(inferred)
                }

        # Show inferred goals with edit fields (review before saving)
        if st.session_state.get("auto_inferred_goals"):
            st.markdown("**Review and edit before saving:**")
            inferred = st.session_state.auto_inferred_goals
            edits = st.session_state.get("auto_inferred_edits", {})

            for i, g in enumerate(inferred):
                c1, c2 = st.columns([3, 1])
                with c1:
                    new_label = st.text_input(
                        f"Goal {i+1}", value=edits.get(i, {}).get("label", g["label"]),
                        key=f"infer_label_{i}",
                    )
                    new_desc = st.text_input(
                        "Description", value=edits.get(i, {}).get("description", g.get("description", "")),
                        key=f"infer_desc_{i}",
                    )
                with c2:
                    if st.button("Remove", key=f"rm_infer_{i}"):
                        st.session_state.auto_inferred_goals.pop(i)
                        st.rerun()
                edits[i] = {"label": new_label, "description": new_desc}
            st.session_state.auto_inferred_edits = edits

            # Allow adding manual goals on top of inferred
            st.markdown("**Add additional goals:**")
            if "extra_goals" not in st.session_state:
                st.session_state.extra_goals = []

            for j, eg in enumerate(st.session_state.extra_goals):
                ec1, ec2 = st.columns([5, 1])
                with ec1:
                    eg["label"] = st.text_input("Label", value=eg["label"], key=f"eg_label_{j}")
                    eg["description"] = st.text_input("Description", value=eg.get("description", ""), key=f"eg_desc_{j}")
                with ec2:
                    if st.button("Remove", key=f"rm_eg_{j}"):
                        st.session_state.extra_goals.pop(j)
                        st.rerun()

            if st.button("+ Add goal", key="add_extra_goal"):
                st.session_state.extra_goals.append({"label": "", "description": ""})
                st.rerun()

            # Build final goals from inferred + extra
            goals = []
            for i, g in enumerate(inferred):
                ed = edits.get(i, {})
                lbl = ed.get("label", g["label"]).strip()
                if lbl:
                    goals.append({"id": f"goal_inf_{i}", "label": lbl,
                                  "description": ed.get("description", ""), "auto_inferred": True})
            for j, eg in enumerate(st.session_state.extra_goals):
                if eg["label"].strip():
                    goals.append({"id": f"goal_extra_{j}", "label": eg["label"].strip(),
                                  "description": eg.get("description", ""), "auto_inferred": False})

    # ── AI FROM DESCRIPTION ──────────────────
    elif goal_input_mode == "Describe what you want (AI generates)":
        user_desc = st.text_area(
            "Describe your career goals in plain text",
            placeholder="e.g. I want to become a Director of Product at a Series B AI startup working on enterprise SaaS...",
            height=120,
            key="goal_desc_input",
        )
        if st.button("Generate goals from description", key="gen_from_desc_btn"):
            if user_desc.strip():
                with st.spinner("Generating goals..."):
                    combined = f"User description: {user_desc}\n\nResume:\n{st.session_state.resume_text[:2000]}"
                    inferred = auto_infer_goals_from_resume(combined)
                    st.session_state.auto_inferred_goals = inferred
                    st.session_state.auto_inferred_edits = {
                        i: {"label": g["label"], "description": g.get("description", "")}
                        for i, g in enumerate(inferred)
                    }
            else:
                st.warning("Enter a description first.")

        # Same review UI as auto-infer
        if st.session_state.get("auto_inferred_goals"):
            st.markdown("**Review and edit:**")
            inferred = st.session_state.auto_inferred_goals
            edits = st.session_state.get("auto_inferred_edits", {})
            for i, g in enumerate(inferred):
                c1, c2 = st.columns([5, 1])
                with c1:
                    new_label = st.text_input(
                        f"Goal {i+1}", value=edits.get(i, {}).get("label", g["label"]),
                        key=f"desc_label_{i}",
                    )
                    new_desc = st.text_input(
                        "Description", value=edits.get(i, {}).get("description", ""),
                        key=f"desc_desc_{i}",
                    )
                with c2:
                    if st.button("Remove", key=f"rm_desc_{i}"):
                        st.session_state.auto_inferred_goals.pop(i)
                        st.rerun()
                edits[i] = {"label": new_label, "description": new_desc}
            st.session_state.auto_inferred_edits = edits
            goals = [
                {"id": f"goal_d_{i}", "label": edits.get(i, {}).get("label", g["label"]).strip(),
                 "description": edits.get(i, {}).get("description", ""), "auto_inferred": True}
                for i, g in enumerate(inferred)
                if edits.get(i, {}).get("label", g["label"]).strip()
            ]

    # ── MANUAL ──────────────────────────────
    else:
        if "manual_goals" not in st.session_state:
            st.session_state.manual_goals = [{"label": "", "description": ""}]

        st.markdown("**Define your goals:**")
        for i, mg in enumerate(st.session_state.manual_goals):
            with st.container():
                st.markdown(
                    f"<div style='background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:12px; margin-bottom:8px;'>",
                    unsafe_allow_html=True,
                )
                c1, c2 = st.columns([5, 1])
                with c1:
                    mg["label"] = st.text_input(
                        f"Goal {i+1} name", value=mg["label"], key=f"mg_label_{i}",
                        placeholder="e.g. Senior Product Manager role"
                    )
                    mg["description"] = st.text_area(
                        "What does success look like?", value=mg.get("description", ""),
                        key=f"mg_desc_{i}", height=70,
                        placeholder="e.g. Leading a team of 5+ PMs at a B2B SaaS company in the AI space"
                    )
                with c2:
                    st.write("")
                    st.write("")
                    if len(st.session_state.manual_goals) > 1:
                        if st.button("Remove", key=f"rm_mg_{i}"):
                            st.session_state.manual_goals.pop(i)
                            st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

        col_add, col_clear = st.columns([1, 1])
        with col_add:
            if st.button("+ Add goal", key="add_manual_goal"):
                st.session_state.manual_goals.append({"label": "", "description": ""})
                st.rerun()
        with col_clear:
            if st.button("Clear all", key="clear_manual_goals"):
                st.session_state.manual_goals = [{"label": "", "description": ""}]
                st.rerun()

        goals = [
            {"id": f"goal_{i}", "label": mg["label"].strip(),
             "description": mg.get("description", ""), "auto_inferred": False}
            for i, mg in enumerate(st.session_state.manual_goals)
            if mg["label"].strip()
        ]

    # ── Save button ──────────────────────────
    st.divider()
    can_create = bool(goals and goal_set_name and goal_set_name.strip())

    if not goal_set_name:
        st.caption("Enter a goal set name above.")
    if not goals:
        st.caption("Add at least one goal with a name.")

    if can_create:
        if st.button("Save Goal Set", use_container_width=True, key="create_gs_btn", type="primary"):
            goal_set_id = str(uuid.uuid4())[:8]
            goal_objects = [
                Goal(
                    id=g["id"], label=g["label"],
                    description=g.get("description", ""),
                    confidence="high",
                    auto_inferred=g.get("auto_inferred", False),
                )
                for g in goals
            ]
            goal_set = GoalSet(
                id=goal_set_id, name=goal_set_name.strip(),
                goals=goal_objects, created_at=datetime.now(), is_active=False,
            )
            st.session_state.goal_sets[goal_set_id] = goal_set
            # Reset form state
            st.session_state.auto_inferred_goals = []
            st.session_state.auto_inferred_edits = {}
            st.session_state.manual_goals = [{"label": "", "description": ""}]
            st.session_state.extra_goals = []
            save_goal_sets(st.session_state.goal_sets, st.session_state.active_goal_set_id)
            st.success(f'Saved "{goal_set_name.strip()}". Activate it above to use it in analysis.')
            st.rerun()