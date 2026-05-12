"""Common components and utilities."""

import streamlit as st
from utils.pdf_viewer import extract_pdf_text_preview

try:
    from utils.pdf_viewer import convert_pdf_to_images
    HAS_PDF2IMAGE = True
except Exception:
    HAS_PDF2IMAGE = False


@st.dialog("📄 PDF Viewer")
def pdf_viewer_modal():
    if not st.session_state.pdf_modal_bytes or not st.session_state.pdf_modal_name:
        st.error("No PDF loaded.")
        return

    st.subheader(st.session_state.pdf_modal_name)

    if HAS_PDF2IMAGE:
        try:
            images = convert_pdf_to_images(st.session_state.pdf_modal_bytes)
            st.caption(f"📄 {len(images)} pages")
            with st.container(height=700, border=True):
                for idx, image in enumerate(images, 1):
                    st.image(image, width=750)
                    st.caption(f"Page {idx} of {len(images)}")
                    if idx < len(images):
                        st.divider()
            return
        except Exception:
            pass

    try:
        preview_text = extract_pdf_text_preview(st.session_state.pdf_modal_bytes)
        st.caption("Text preview (install poppler for image rendering)")
        st.text_area("Content", preview_text, height=500, disabled=True)
    except Exception as e:
        st.error(f"Could not display PDF: {str(e)}")


def render_pdf_modal():
    if st.session_state.show_pdf_modal:
        pdf_viewer_modal()
        st.session_state.show_pdf_modal = False