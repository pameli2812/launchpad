"""Setup tab - Resume upload and goal management."""

import streamlit as st
import uuid
from datetime import datetime
from typing import Optional

from utils.parser import extract_text_from_pdf, extract_text_from_docx
from utils.goal_inference import auto_infer_goals_from_resume
from utils.pdf_viewer import save_pdf_locally, get_uploaded_pdfs, load_pdf_bytes, delete_pdf
from utils.models import Goal, GoalSet


def render_setup_tab():
    """Render the Setup tab content."""
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
            goal_input_mode = st.radio("How to set goals?", ["Manual", "Auto-infer"], index=0)
        
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
            num_goals = st.number_input("Number of goals", 1, 7, 1)
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
                    st.write("✓ Active")
            with col3:
                if st.button("Delete", key=f"del_{gs_id}"):
                    del st.session_state.goal_sets[gs_id]
                    st.rerun()
    else:
        st.info("No goal sets yet")
