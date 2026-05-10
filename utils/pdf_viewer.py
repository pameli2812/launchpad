"""PDF viewer utility for Streamlit."""

from pdf2image import convert_from_bytes
from PIL import Image
from typing import List


def convert_pdf_to_images(pdf_bytes: bytes, first_n_pages: int = None) -> List[Image.Image]:
    """Convert PDF bytes to list of PIL Image objects."""
    try:
        images = convert_from_bytes(pdf_bytes, first_page=1, last_page=first_n_pages)
        return images
    except Exception as e:
        raise Exception(f"Error converting PDF to images: {str(e)}")


def get_pdf_page_count(pdf_bytes: bytes) -> int:
    """Get total number of pages in PDF."""
    try:
        images = convert_from_bytes(pdf_bytes)
        return len(images)
    except Exception as e:
        raise Exception(f"Error reading PDF: {str(e)}")
