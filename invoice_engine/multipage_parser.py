"""
multipage_parser.py
-------------------
Multi-page invoice parser that integrates with the production extraction pipeline.
This module bridges the old api_server.py with the new extraction system.
"""

import logging
from typing import Dict, Any, Union
from pathlib import Path

from invoice_engine.pdf_processor import PDFProcessor
from invoice_engine.ocr_engine_paddle import OCREngine, OCREngineFallback, PADDLEOCR_AVAILABLE
from invoice_engine.schema_loader import get_universal_schema
from invoice_engine.invoice_mapper import InvoiceMapper

logger = logging.getLogger(__name__)


def parse_multipage_invoice(pdf_path: Union[str, Path]) -> Dict[str, Any]:
    """
    Parse a multi-page invoice PDF and return structured JSON.
    
    This function uses OCR-based extraction without LLM for faster processing.
    It's used as a fallback in the legacy api_server.py system.
    
    Args:
        pdf_path: Path to the PDF file
    
    Returns:
        Dictionary with extracted invoice data matching universal schema
    """
    try:
        logger.info(f"Parsing multi-page invoice: {pdf_path}")
        
        # Initialize components
        pdf_processor = PDFProcessor(poppler_path=None)
        
        # Use OCR engine
        if PADDLEOCR_AVAILABLE:
            try:
                ocr_engine = OCREngine(use_angle_cls=True, lang="en")
                logger.info("Using PaddleOCR engine")
            except Exception as e:
                logger.warning(f"PaddleOCR init failed, using fallback: {e}")
                ocr_engine = OCREngineFallback()
        else:
            ocr_engine = OCREngineFallback()
            logger.info("Using Tesseract fallback engine")
        
        # Convert PDF to images
        page_images = pdf_processor.convert_pdf_to_images(str(pdf_path), dpi=300)
        logger.info(f"Converted {len(page_images)} page(s)")
        
        # OCR each page
        page_texts = ocr_engine.extract_text_from_images(page_images)
        logger.info(f"Extracted text from {len(page_texts)} page(s)")
        
        # Combine text
        combined_text = ocr_engine.merge_page_texts(page_texts)
        
        # Parse with rule-based extraction
        result = _rule_based_extraction(combined_text)
        
        # Map to schema
        mapper = InvoiceMapper()
        result = mapper.map_to_schema(result)
        
        # Add metadata
        result = mapper.add_metadata(result, {
            "method": "multipage_ocr",
            "pages": len(page_images),
            "extraction_type": "rule_based"
        })
        
        logger.info("Multi-page parsing completed successfully")
        return result
        
    except Exception as e:
        logger.error(f"Multi-page parsing failed: {str(e)}")
        
        # Return empty schema with error
        schema = get_universal_schema()
        mapper = InvoiceMapper()
        schema = mapper.add_metadata(schema, {
            "method": "multipage_ocr",
            "pages": 0,
            "error": str(e),
            "status": "NEEDS_REVIEW"
        })
        
        return schema


def _rule_based_extraction(text: str) -> Dict[str, Any]:
    """
    Simple rule-based extraction from OCR text.
    
    This is a basic implementation that looks for common patterns.
    For better accuracy, use the Gemini-based extraction in main.py.
    
    Args:
        text: Combined OCR text from all pages
    
    Returns:
        Partially filled invoice data dict
    """
    import re
    
    result = {}
    
    # Try to extract invoice number
    invoice_patterns = [
        r"invoice\s*(?:number|no|#)[\s:]*([A-Z0-9\-/]+)",
        r"inv\s*(?:no|#)[\s:]*([A-Z0-9\-/]+)",
        r"bill\s*(?:no|#)[\s:]*([A-Z0-9\-/]+)"
    ]
    
    for pattern in invoice_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result.setdefault("header", {}).setdefault("invoice_details", {})["invoice_number"] = match.group(1)
            break
    
    # Try to extract date
    date_patterns = [
        r"date[\s:]*(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})",
        r"(\d{1,2}[-/]\d{1,2}[-/]\d{2,4})"
    ]
    
    for pattern in date_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            result.setdefault("header", {}).setdefault("invoice_details", {})["invoice_date"] = match.group(1)
            break
    
    # Try to extract total
    total_patterns = [
        r"total[\s:]*([0-9,]+\.?\d*)",
        r"amount[\s:]*([0-9,]+\.?\d*)",
        r"grand\s*total[\s:]*([0-9,]+\.?\d*)"
    ]
    
    for pattern in total_patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                total_val = float(match.group(1).replace(",", ""))
                result.setdefault("summary", {})["total_amount"] = total_val
                break
            except:
                pass
    
    # Try to extract company name (first capitalized line)
    lines = text.split("\n")
    for line in lines[:10]:  # Check first 10 lines
        line = line.strip()
        if len(line) > 3 and line[0].isupper():
            result.setdefault("header", {}).setdefault("vendor_details", {})["company_name_en"] = line
            break
    
    return result
