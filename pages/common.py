"""Common components and utilities."""

import streamlit as st
from utils.pdf_viewer import convert_pdf_to_images, extract_pdf_text_preview


@st.dialog("📄 PDF Viewer")
def pdf_viewer_modal():
    """Display PDF viewer in a modal dialog with scrollable pages."""
    if st.session_state.pdf_modal_bytes and st.session_state.pdf_modal_name:
        st.subheader(st.session_state.pdf_modal_name)
        
        try:
            images = convert_pdf_to_images(st.session_state.pdf_modal_bytes)
            total_pages = len(images)
            
            st.caption(f"📄 {total_pages} pages • Scroll to view")
            
            # Scrollable container with all pages
            with st.container(height=700, border=True):
                for idx, image in enumerate(images, 1):
                    st.image(image, width=750)
                    st.caption(f"Page {idx} of {total_pages}")
                    if idx < len(images):
                        st.divider()
            
        except Exception as e:
            st.warning("⚠️ Image preview unavailable (poppler not installed)")
            try:
                preview_text = extract_pdf_text_preview(st.session_state.pdf_modal_bytes)
                st.text_area("Text Preview", preview_text, height=300, disabled=True)
            except:
                st.error("Could not display PDF")


def render_pdf_modal():
    """Show PDF modal if triggered."""
    if st.session_state.show_pdf_modal:
        pdf_viewer_modal()
        # Reset the modal flag after showing
        st.session_state.show_pdf_modal = False
