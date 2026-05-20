"""Apply approved suggestions to a resume PDF while preserving the template.

Uses PyMuPDF redaction:
- Text Edit / Polish Content: locate the original text, redact the area, and
  re-render the replacement in the same rectangle (keeps the surrounding layout).
- Remove Text: locate and redact (no replacement).
- Add Data: collected and appended on a clearly-marked new page at the end,
  since deciding where to splice new content into an arbitrary resume template
  isn't reliably automatable.

Returns the modified PDF bytes. The original file on disk is never touched.
"""

from __future__ import annotations

from typing import Any, Dict, List, Tuple

import fitz  # PyMuPDF


def _normalize_whitespace(s: str) -> str:
    return " ".join(s.split())


def _find_text_rect(doc: fitz.Document, needle: str) -> Tuple[int, fitz.Rect] | None:
    """Locate the first occurrence of `needle` across all pages.

    Tries exact match, then whitespace-collapsed match, then a shorter prefix
    so multi-line strings have a fighting chance of being found.
    """
    if not needle:
        return None

    candidates = [needle, _normalize_whitespace(needle)]
    # Multi-line strings rarely match verbatim — fall back to the first ~40 chars
    if len(needle) > 40:
        candidates.append(needle[:40])
        candidates.append(_normalize_whitespace(needle)[:40])

    for candidate in candidates:
        for page_num in range(len(doc)):
            page = doc[page_num]
            rects = page.search_for(candidate)
            if rects:
                return page_num, rects[0]
    return None


def _detect_fontsize(page: fitz.Page, rect: fitz.Rect, default: float = 10.0) -> float:
    """Best-effort font size detection by scanning text spans overlapping `rect`."""
    try:
        for block in page.get_text("dict").get("blocks", []):
            for line in block.get("lines", []):
                for span in line.get("spans", []):
                    span_rect = fitz.Rect(span["bbox"])
                    if span_rect.intersects(rect):
                        size = span.get("size")
                        if size:
                            return float(size)
    except Exception:
        pass
    return default


def apply_changes(pdf_bytes: bytes, changes: List[Dict[str, Any]]) -> Tuple[bytes, Dict[str, Any]]:
    """Apply a list of accepted suggestions to the PDF.

    Each change is `{type, section, before, after}`. Returns (modified_bytes, report)
    where `report` summarizes which changes were applied vs skipped.
    """
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    additions: List[Tuple[str, str]] = []
    applied: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []

    # Pass 1: queue redactions per page so all replacements on a page can be
    # applied together (apply_redactions is per-page).
    redactions_per_page: Dict[int, list] = {}

    for change in changes:
        ctype = str(change.get("type", "")).strip().lower()
        before = str(change.get("before", "") or "").strip()
        after = str(change.get("after", "") or "").strip()
        section = str(change.get("section", "") or "")

        if ctype in ("text edit", "polish content"):
            if not before:
                skipped.append({**change, "reason": "missing original text"})
                continue
            located = _find_text_rect(doc, before)
            if not located:
                skipped.append({**change, "reason": "original text not found in PDF"})
                continue
            page_num, rect = located
            page = doc[page_num]
            fontsize = _detect_fontsize(page, rect)
            # Reserve a bit more height if the replacement is longer.
            if len(after) > len(before) * 1.3:
                rect = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1 + fontsize * 1.2)
            redactions_per_page.setdefault(page_num, []).append(
                {"rect": rect, "text": after, "fontsize": fontsize}
            )
            applied.append(change)

        elif ctype == "remove text":
            if not before:
                skipped.append({**change, "reason": "missing target text"})
                continue
            located = _find_text_rect(doc, before)
            if not located:
                skipped.append({**change, "reason": "target text not found in PDF"})
                continue
            page_num, rect = located
            redactions_per_page.setdefault(page_num, []).append(
                {"rect": rect, "text": "", "fontsize": 10.0}
            )
            applied.append(change)

        elif ctype == "add data":
            if not after:
                skipped.append({**change, "reason": "nothing to add"})
                continue
            additions.append((section or "Additions", after))
            applied.append(change)

        else:
            skipped.append({**change, "reason": f"unknown suggestion type '{ctype}'"})

    # Pass 2: apply redactions per page.
    for page_num, items in redactions_per_page.items():
        page = doc[page_num]
        for item in items:
            page.add_redact_annot(item["rect"], text=item["text"], fontsize=item["fontsize"])
        # images=0 / graphics=0 leaves the surrounding template untouched.
        page.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)

    # Pass 3: append an "AI-suggested additions" page if needed.
    if additions:
        page = doc.new_page()
        margin = 50
        rect = fitz.Rect(margin, margin, page.rect.width - margin, page.rect.height - margin)
        body = "AI-Suggested Additions\n\n"
        body += "These items were approved during your resume analysis.\n"
        body += "Review and integrate them into the appropriate sections of your resume.\n\n"
        for section, content in additions:
            body += f"[{section}]\n{content}\n\n"
        page.insert_textbox(rect, body, fontsize=11, fontname="helv", align=0)

    output = doc.tobytes()
    doc.close()

    return output, {
        "applied_count": len(applied),
        "skipped_count": len(skipped),
        "skipped": skipped,
    }
