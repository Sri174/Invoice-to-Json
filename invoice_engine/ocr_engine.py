import hashlib
import io
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Any, Tuple

import cv2
import numpy as np
from PIL import Image
import pytesseract


logger = logging.getLogger(__name__)

# Simple in-memory cache: hash(image_bytes) -> {text, confidence}
_OCR_CACHE: Dict[str, Dict[str, Any]] = {}
_EXECUTOR = ThreadPoolExecutor(max_workers=4)


def _hash_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def _preprocess_image(image_bytes: bytes) -> Any:
    """Preprocess image for better OCR results.
    
    Steps:
    1. Convert to grayscale
    2. Apply Gaussian blur to reduce noise
    3. Apply adaptive threshold for binarization
    4. Apply sharpening filter
    """
    image = Image.open(io.BytesIO(image_bytes)).convert("L")  # grayscale
    img = np.array(image)

    # Apply Gaussian blur to reduce noise
    img = cv2.GaussianBlur(img, (5, 5), 0)

    # Adaptive threshold for binarization
    img = cv2.adaptiveThreshold(
        img,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        15,
    )

    # Sharpen to enhance text edges
    kernel = np.array([[0, -1, 0], [-1, 5, -1], [0, -1, 0]])
    img = cv2.filter2D(img, -1, kernel)

    return img


def _tesseract_variants(img) -> List[Tuple[str, float, str, Dict[str, Any]]]:
    """Run multiple Tesseract configs and score outputs.

    Returns list of (text, composite_score, config_label, score_breakdown).
    
    Scoring criteria:
    - Confidence: average OCR confidence (0-100)
    - Numeric tokens: count of tokens containing digits (important for invoices)
    - Word count: total number of valid words
    
    Composite score balances all three factors.
    """
    variants = [
        ("oem3_psm6", "--oem 3 --psm 6"),
        ("oem3_psm4", "--oem 3 --psm 4"),
    ]

    results: List[Tuple[str, float, str, Dict[str, Any]]] = []
    for label, config in variants:
        try:
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT, config=config)
            words = data.get("text", [])
            confs = data.get("conf", [])
            text = " ".join(w for w in words if w and w.strip())

            # Confidence: average over valid entries
            scores = [float(c) for c in confs if str(c).isdigit() and int(float(c)) >= 0]
            avg_conf = sum(scores) / len(scores) if scores else 0.0

            # Word count: number of valid words
            valid_words = [w for w in words if w and w.strip() and len(w.strip()) > 1]
            word_count = len(valid_words)

            # Numeric tokens: count words containing digits (invoices have many numbers)
            numeric_tokens = sum(1 for w in valid_words if any(c.isdigit() for c in w))

            # Composite score: weighted combination
            # Confidence is primary (0-100 range)
            # Word count normalized to 0-100 (assume 100+ words is good)
            # Numeric tokens normalized to 0-100 (assume 20+ numeric tokens is good)
            normalized_word_count = min(100, (word_count / 100) * 100)
            normalized_numeric = min(100, (numeric_tokens / 20) * 100)
            
            composite_score = (
                avg_conf * 0.5 +  # 50% weight on confidence
                normalized_numeric * 0.35 +  # 35% weight on numeric content
                normalized_word_count * 0.15  # 15% weight on word count
            )

            score_breakdown = {
                "confidence": avg_conf,
                "word_count": word_count,
                "numeric_tokens": numeric_tokens,
                "normalized_word_count": normalized_word_count,
                "normalized_numeric": normalized_numeric,
                "composite_score": composite_score,
            }

            results.append((text, composite_score, label, score_breakdown))
            
        except Exception as e:
            logger.warning("[OCR] Tesseract variant %s failed: %s", label, e)

    return results


def ocr_page(image_bytes: bytes) -> Dict[str, Any]:
    """Run OCR on a single page with preprocessing and variant scoring.
    
    Returns the best OCR variant based on composite scoring.
    """
    key = _hash_bytes(image_bytes)
    if key in _OCR_CACHE:
        cached = _OCR_CACHE[key]
        logger.debug("[OCR] Using cached OCR result for key=%s", key)
        return cached

    img = _preprocess_image(image_bytes)
    variants = _tesseract_variants(img)

    if not variants:
        result = {"text": "", "confidence": 0.0, "variant": None, "scores": {}}
        _OCR_CACHE[key] = result
        return result

    # Select best by composite score
    best_text, best_score, best_label, best_breakdown = max(variants, key=lambda v: v[1])
    
    logger.info(
        "[OCR] Best variant: %s | composite_score=%.2f | confidence=%.2f | words=%d | numeric=%d",
        best_label,
        best_breakdown["composite_score"],
        best_breakdown["confidence"],
        best_breakdown["word_count"],
        best_breakdown["numeric_tokens"],
    )
    
    result = {
        "text": best_text,
        "confidence": best_breakdown["confidence"],
        "variant": best_label,
        "scores": best_breakdown,
    }
    _OCR_CACHE[key] = result
    return result


def ocr_pages_parallel(page_images: List[bytes]) -> Tuple[str, List[Dict[str, Any]]]:
    """OCR multiple pages in parallel and merge text.

    Returns overall_text, per_page_debug
    """
    futures = { _EXECUTOR.submit(ocr_page, img): idx for idx, img in enumerate(page_images) }
    per_page: List[Dict[str, Any]] = [None] * len(page_images)

    for future in as_completed(futures):
        idx = futures[future]
        try:
            per_page[idx] = future.result()
        except Exception as e:
            logger.error("[OCR] Page %d OCR failed: %s", idx, e)
            per_page[idx] = {
                "text": "", 
                "confidence": 0.0, 
                "variant": None, 
                "scores": {}, 
                "error": str(e)
            }

    merged_text_parts = []
    for idx, page in enumerate(per_page):
        page_text = page.get("text", "") if page else ""
        merged_text_parts.append(f"\n\n===== PAGE {idx+1} =====\n\n{page_text}")

    merged_text = "".join(merged_text_parts)
    return merged_text, per_page
