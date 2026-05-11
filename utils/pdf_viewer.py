"""PDF viewer utility for Streamlit."""

import os
import shutil
from pathlib import Path
import hashlib
from datetime import datetime

try:
    from pdf2image import convert_from_bytes
    HAS_PDF2IMAGE = True
except ImportError:
    HAS_PDF2IMAGE = False

from PIL import Image
from PyPDF2 import PdfReader
from io import BytesIO
from typing import List, Optional, Dict


# Data storage paths
UPLOAD_DIR = Path(__file__).parent.parent / "data" / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


def save_pdf_locally(pdf_bytes: bytes, filename: str) -> str:
    """Save PDF to local storage and return the file path."""
    try:
        # Create safe filename
        safe_name = "".join(c for c in filename if c.isalnum() or c in ('-', '_', '.'))
        if not safe_name.endswith('.pdf'):
            safe_name += '.pdf'
        
        # Add timestamp to make unique
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name_parts = safe_name.rsplit('.', 1)
        unique_name = f"{name_parts[0]}_{timestamp}.pdf"
        
        file_path = UPLOAD_DIR / unique_name
        with open(file_path, 'wb') as f:
            f.write(pdf_bytes)
        
        return str(file_path)
    except Exception as e:
        raise Exception(f"Error saving PDF: {str(e)}")


def get_uploaded_pdfs() -> List[Dict[str, str]]:
    """Get list of recently uploaded PDFs."""
    try:
        pdfs = []
        if UPLOAD_DIR.exists():
            for pdf_file in sorted(UPLOAD_DIR.glob("*.pdf"), key=os.path.getmtime, reverse=True):
                pdfs.append({
                    "name": pdf_file.name,
                    "path": str(pdf_file),
                    "size": pdf_file.stat().st_size,
                    "modified": datetime.fromtimestamp(pdf_file.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
                })
        return pdfs
    except Exception as e:
        raise Exception(f"Error reading uploaded PDFs: {str(e)}")


def delete_pdf(file_path: str) -> bool:
    """Delete a saved PDF file."""
    try:
        Path(file_path).unlink()
        return True
    except Exception as e:
        raise Exception(f"Error deleting PDF: {str(e)}")


def load_pdf_bytes(file_path: str) -> bytes:
    """Load PDF bytes from file."""
    try:
        with open(file_path, 'rb') as f:
            return f.read()
    except Exception as e:
        raise Exception(f"Error loading PDF: {str(e)}")


def convert_pdf_to_images(pdf_bytes: bytes, first_n_pages: int = None) -> List[Image.Image]:
    """Convert PDF bytes to list of PIL Image objects. Requires poppler."""
    if not HAS_PDF2IMAGE:
        raise Exception("pdf2image not available. Please install: pip install pdf2image")
    
    try:
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=first_n_pages)
        return images
    except Exception as e:
        raise Exception(f"Error converting PDF to images: {str(e)}\nNote: poppler must be installed. On macOS: brew install poppler")


def get_pdf_page_count(pdf_bytes: bytes) -> int:
    """Get total number of pages in PDF."""
    try:
        if HAS_PDF2IMAGE:
            images = convert_from_bytes(pdf_bytes)
            return len(images)
        else:
            # Fallback: use PyPDF2 to count pages
            pdf = PdfReader(BytesIO(pdf_bytes))
            return len(pdf.pages)
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")


def extract_pdf_text_preview(pdf_bytes: bytes, max_pages: int = 3) -> str:
    """Extract text from first N pages of PDF as fallback preview."""
    try:
        pdf = PdfReader(BytesIO(pdf_bytes))
        text = ""
        for i, page in enumerate(pdf.pages[:max_pages]):
            text += f"\n--- Page {i+1} ---\n"
            text += page.extract_text()
        return text
    except Exception as e:
        raise Exception(f"Error extracting PDF text: {str(e)}")