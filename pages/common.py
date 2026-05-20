"""Common components and utilities."""

import streamlit as st
from analyser.launchpad.utils.pdf_viewer import extract_pdf_text_preview

try:
    from analyser.launchpad.utils.pdf_viewer import convert_pdf_to_images
    HAS_PDF2IMAGE = True
except Exception:
    HAS_PDF2IMAGE = False


@st.dialog("PDF Viewer")
def pdf_viewer_modal():
    # Force light styling inside the dialog
    st.markdown(
        """
        <style>
        /* Dialog backdrop and container */
        div[data-testid="stDialog"],
        div[data-testid="stDialog"] > div,
        div[role="dialog"],
        div[role="dialog"] > div {
            background-color: #ffffff !important;
            color: #1a1a2e !important;
        }

        /* All text inside dialog */
        div[role="dialog"] p,
        div[role="dialog"] span,
        div[role="dialog"] h1,
        div[role="dialog"] h2,
        div[role="dialog"] h3,
        div[role="dialog"] label,
        div[role="dialog"] .stMarkdown,
        div[role="dialog"] [data-testid="stText"],
        div[role="dialog"] [data-testid="stCaptionContainer"] * {
            color: #1a1a2e !important;
        }

        /* Subheader inside dialog */
        div[role="dialog"] [data-testid="stHeading"] {
            color: #1a1a2e !important;
        }

        /* Scrollable container inside dialog */
        div[role="dialog"] [data-testid="stVerticalBlockBorderWrapper"],
        div[role="dialog"] [data-testid="element-container"] {
            background-color: #ffffff !important;
        }

        /* Close button */
        div[role="dialog"] button[aria-label="Close"] {
            color: #1a1a2e !important;
        }

        /* Text area inside dialog (fallback text view) */
        div[role="dialog"] textarea {
            background-color: #f8f9fb !important;
            color: #1a1a2e !important;
            border: 1px solid #cbd5e1 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    if not st.session_state.get("pdf_modal_bytes") or not st.session_state.get("pdf_modal_name"):
        st.error("No PDF loaded.")
        return

    st.subheader(st.session_state.pdf_modal_name)

    if HAS_PDF2IMAGE:
        try:
            images = convert_pdf_to_images(st.session_state.pdf_modal_bytes)
            st.caption(f"{len(images)} pages")
            with st.container(height=600, border=False):
                for idx, image in enumerate(images, 1):
                    st.image(image, use_container_width=True)
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
    if st.session_state.get("show_pdf_modal"):
        pdf_viewer_modal()
        st.session_state.show_pdf_modal = False