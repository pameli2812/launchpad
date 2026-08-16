"""PDF viewer utility for Streamlit."""

import os
from pathlib import Path
from datetime import datetime
from typing import List, Dict
from io import BytesIO

import fitz  # PyMuPDF
from PIL import Image
from PyPDF2 import PdfReader


# -----------------------------------
# Data storage path
# -----------------------------------

UPLOAD_DIR = (
    Path(__file__).parent.parent
    / "data"
    / "uploads"
)

UPLOAD_DIR.mkdir(
    parents=True,
    exist_ok=True
)


# -----------------------------------
# Save PDF locally
# -----------------------------------

def save_pdf_locally(
    pdf_bytes: bytes,
    filename: str
) -> str:
    """
    Save PDF locally preserving the original filename (including spaces).
    If the same name is uploaded again, append a timestamp suffix so users
    can tell duplicates apart by upload time.
    """

    try:
        # Only strip path separators / control chars — keep spaces & unicode
        safe_name = "".join(
            c for c in filename
            if c not in ("/", "\\", "\x00")
            and (c.isprintable() or c == " ")
        ).strip()

        if not safe_name.lower().endswith(".pdf"):
            safe_name += ".pdf"

        base_name, extension = safe_name.rsplit(".", 1)

        file_path = UPLOAD_DIR / safe_name

        if file_path.exists():
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            versioned_name = f"{base_name}_{timestamp}.{extension}"
            file_path = UPLOAD_DIR / versioned_name

        with open(file_path, "wb") as f:
            f.write(pdf_bytes)

        return str(file_path)

    except Exception as e:
        raise Exception(
            f"Error saving PDF: {str(e)}"
        )


# -----------------------------------
# Get uploaded PDFs
# -----------------------------------

def get_uploaded_pdfs() -> List[Dict]:
    """
    Return uploaded PDFs.
    """

    try:
        pdfs = []

        if UPLOAD_DIR.exists():

            for pdf_file in sorted(
                UPLOAD_DIR.glob("*.pdf"),
                key=os.path.getmtime,
                reverse=True
            ):

                pdfs.append({
                    "name": pdf_file.name,
                    "path": str(pdf_file),
                    "size": pdf_file.stat().st_size,
                    "modified":
                    datetime.fromtimestamp(
                        pdf_file.stat().st_mtime
                    ).strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                })

        return pdfs

    except Exception as e:
        raise Exception(
            f"Error reading PDFs: {str(e)}"
        )


# -----------------------------------
# Delete PDF
# -----------------------------------

def delete_pdf(
    file_path: str
) -> bool:
    """
    Delete PDF file.
    """

    try:
        Path(file_path).unlink()
        return True

    except Exception as e:
        raise Exception(
            f"Error deleting PDF: {str(e)}"
        )


# -----------------------------------
# Load PDF bytes
# -----------------------------------

def load_pdf_bytes(
    file_path: str
) -> bytes:
    """
    Load PDF bytes.
    """

    try:
        with open(file_path, "rb") as f:
            return f.read()

    except Exception as e:
        raise Exception(
            f"Error loading PDF: {str(e)}"
        )


# -----------------------------------
# Convert PDF to images
# NO POPPLER REQUIRED
# -----------------------------------

def convert_pdf_to_images(
    pdf_bytes: bytes,
    first_n_pages: int = None
):
    """
    Convert PDF to PIL images
    using PyMuPDF.
    """

    try:

        images = []

        pdf_document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        total_pages = len(pdf_document)

        if first_n_pages:
            total_pages = min(
                total_pages,
                first_n_pages
            )

        for page_num in range(
            total_pages
        ):

            page = pdf_document[
                page_num
            ]

            # better quality
            matrix = fitz.Matrix(
                2,
                2
            )

            pix = page.get_pixmap(
                matrix=matrix,
                alpha=False
            )

            image_bytes = pix.tobytes(
                "png"
            )

            image = Image.open(
                BytesIO(image_bytes)
            )

            images.append(image)

        pdf_document.close()

        return images

    except Exception as e:
        raise Exception(
            f"Error converting PDF: "
            f"{str(e)}"
        )


# -----------------------------------
# Page count
# -----------------------------------

def get_pdf_page_count(
    pdf_bytes: bytes
) -> int:
    """
    Get total PDF pages.
    """

    try:
        pdf_document = fitz.open(
            stream=pdf_bytes,
            filetype="pdf"
        )

        count = len(pdf_document)

        pdf_document.close()

        return count

    except Exception:

        try:
            pdf = PdfReader(
                BytesIO(pdf_bytes)
            )

            return len(pdf.pages)

        except Exception as e:
            raise Exception(
                f"Error reading PDF: "
                f"{str(e)}"
            )


# -----------------------------------
# Text preview fallback
# -----------------------------------

def extract_pdf_text_preview(
    pdf_bytes: bytes,
    max_pages: int = 3
) -> str:
    """
    Extract text preview.
    """

    try:
        pdf = PdfReader(
            BytesIO(pdf_bytes)
        )

        text = ""

        for i, page in enumerate(
            pdf.pages[:max_pages]
        ):

            text += (
                f"\n--- Page {i+1} ---\n"
            )

            extracted = (
                page.extract_text()
            )

            if extracted:
                text += extracted

        return text.strip()

    except Exception as e:
        raise Exception(
            f"Error extracting PDF "
            f"text: {str(e)}"
        )