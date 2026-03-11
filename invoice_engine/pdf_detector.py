"""
pdf_detector.py
---------------
Detect invoice type (digital vs scanned) and derive extraction strategy.

Functions:
- detect_pdf_type(pdf_path) -> "digital" | "scanned" | "mixed" | "unknown"
- extract_text_from_digital_pdf(pdf_path) -> str
- convert_pdf_to_images(pdf_path, max_pages=3, dpi=150, include_last_page=True) -> List[bytes]
- get_extraction_strategy(pdf_path) -> (pdf_type, strategy_dict)
"""
from typing import List, Tuple, Literal, Dict, Any

try:
    import pdfplumber
    _PDFPLUMBER_AVAILABLE = True
except Exception:
    pdfplumber = None
    _PDFPLUMBER_AVAILABLE = False

try:
    from pdf2image import convert_from_path
    _PDF2IMAGE_AVAILABLE = True
except Exception:
    convert_from_path = None
    _PDF2IMAGE_AVAILABLE = False

from io import BytesIO
from PIL import Image

PDFType = Literal["digital", "scanned", "mixed", "unknown"]


def detect_pdf_type(pdf_path: str, text_threshold: int = 50) -> PDFType:
    """Detect whether a PDF is digital (selectable text) or scanned (image-based).

    We inspect up to the first 3 pages with pdfplumber and measure character count.
    """
    if not _PDFPLUMBER_AVAILABLE:
        print("[PDF Detector] pdfplumber not available; cannot detect PDF type")
        return "unknown"

    try:
        with pdfplumber.open(pdf_path) as pdf:
            total_pages = len(pdf.pages)
            if total_pages == 0:
                return "unknown"

            pages_to_check = min(3, total_pages)
            text_pages = 0
            image_pages = 0

            for i in range(pages_to_check):
                page = pdf.pages[i]
                text = page.extract_text() or ""
                char_count = len("".join(text.split()))
                if char_count >= text_threshold:
                    text_pages += 1
                else:
                    image_pages += 1

            if text_pages == pages_to_check:
                return "digital"
            if image_pages == pages_to_check:
                return "scanned"
            return "mixed"
    except Exception as e:
        print(f"[PDF Detector] Error detecting PDF type: {e}")
        return "unknown"


def extract_text_from_digital_pdf(pdf_path: str) -> str:
    """Extract text from all pages of a digital PDF.

    Returns a single string with per-page separators.
    """
    if not _PDFPLUMBER_AVAILABLE:
        return ""

    try:
        chunks: List[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for i, page in enumerate(pdf.pages, start=1):
                text = page.extract_text()
                if text:
                    chunks.append(f"--- PAGE {i} ---\n{text}")
        return "\n\n".join(chunks)
    except Exception as e:
        print(f"[PDF Detector] Error extracting text: {e}")
        return ""


def convert_pdf_to_images(pdf_path: str, max_pages: int = 3, dpi: int = 150, include_last_page: bool = True) -> List[bytes]:
    """Convert PDF pages to JPEG bytes with smart page selection.

    - Uses low DPI (150) for faster processing.
    - Limits to max_pages and always includes last page for totals when possible.
    """
    if not _PDF2IMAGE_AVAILABLE:
        print("[PDF Detector] pdf2image not available; cannot convert to images")
        return []

    try:
        images = convert_from_path(pdf_path, dpi=dpi)
        total = len(images)
        if total == 0:
            return []

        if total <= max_pages:
            selected = images
        else:
            if include_last_page and max_pages >= 2:
                selected = images[: max_pages - 1] + [images[-1]]
            else:
                selected = images[:max_pages]

        out: List[bytes] = []
        for img in selected:
            if img.mode != "RGB":
                img = img.convert("RGB")
            buf = BytesIO()
            img.save(buf, format="JPEG", quality=85)
            out.append(buf.getvalue())
        print(f"[PDF Detector] Converted {len(selected)} pages (of {total}) at {dpi} DPI")
        return out
    except Exception as e:
        print(f"[PDF Detector] Error converting PDF to images: {e}")
        return []


def get_extraction_strategy(pdf_path: str) -> Tuple[PDFType, Dict[str, Any]]:
    """Return (pdf_type, strategy) for this PDF.

    Strategy example:
    {
        "method": "text" | "vision",
        "use_text_extraction": bool,
        "use_vision_extraction": bool,
        "convert_to_images": bool,
        "max_pages": int,
        "dpi": int,
    }
    """
    pdf_type = detect_pdf_type(pdf_path)

    if pdf_type == "digital":
        return pdf_type, {
            "method": "text",
            "use_text_extraction": True,
            "use_vision_extraction": False,
            "convert_to_images": False,
            "max_pages": 10,
            "dpi": None,
        }

    # For scanned, mixed, unknown – default to vision
    return pdf_type, {
        "method": "vision",
        "use_text_extraction": False,
        "use_vision_extraction": True,
        "convert_to_images": True,
        "max_pages": 3,
        "dpi": 150,
    }
