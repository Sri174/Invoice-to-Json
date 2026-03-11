"""
ocr_engine_paddle.py
--------------------
OCR engine using PaddleOCR for text extraction from invoice images.
Provides better accuracy than Tesseract for multi-page invoices.
"""

import numpy as np
from typing import List, Union
from PIL import Image
import logging

try:
    from paddleocr import PaddleOCR
    PADDLEOCR_AVAILABLE = True
except ImportError:
    PADDLEOCR_AVAILABLE = False
    PaddleOCR = None

logger = logging.getLogger(__name__)


class OCREngine:
    """Handles OCR text extraction using PaddleOCR."""
    
    def __init__(self, use_angle_cls: bool = True, lang: str = "en"):
        """
        Initialize PaddleOCR engine.
        
        Args:
            use_angle_cls: Enable angle classification for rotated text
            lang: Language for OCR (default: "en")
        
        Raises:
            ImportError: If PaddleOCR is not installed
        """
        if not PADDLEOCR_AVAILABLE:
            raise ImportError(
                "PaddleOCR is not installed. "
                "Install it with: pip install paddleocr paddlepaddle"
            )
        
        try:
            logger.info(f"Initializing PaddleOCR with lang={lang}, use_angle_cls={use_angle_cls}")
            self.ocr = PaddleOCR(
                use_angle_cls=use_angle_cls,
                lang=lang,
                show_log=False,
                use_gpu=False  # Set to True if CUDA is available
            )
            logger.info("PaddleOCR initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize PaddleOCR: {str(e)}")
            raise
    
    def extract_text_from_image(self, image: Union[Image.Image, np.ndarray]) -> str:
        """
        Extract text from a single image using OCR.
        
        Args:
            image: PIL Image or numpy array
        
        Returns:
            Extracted text as string
        """
        try:
            # Convert PIL Image to numpy array if needed
            if isinstance(image, Image.Image):
                img_array = np.array(image)
            else:
                img_array = image
            
            logger.info(f"Running OCR on image with shape: {img_array.shape}")
            
            # Run OCR
            result = self.ocr.ocr(img_array, cls=True)
            
            # Extract text from result
            text = self._parse_ocr_result(result)
            
            logger.info(f"Extracted {len(text)} characters from image")
            return text
            
        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}")
            return ""
    
    def extract_text_from_images(self, images: List[Union[Image.Image, np.ndarray]]) -> List[str]:
        """
        Extract text from multiple images (e.g., multi-page PDF).
        
        Args:
            images: List of PIL Images or numpy arrays
        
        Returns:
            List of extracted text strings, one per image
        """
        page_texts = []
        
        for i, image in enumerate(images, 1):
            logger.info(f"Processing page {i}/{len(images)}")
            text = self.extract_text_from_image(image)
            page_texts.append(text)
        
        logger.info(f"Extracted text from {len(page_texts)} page(s)")
        return page_texts
    
    def merge_page_texts(self, page_texts: List[str]) -> str:
        """
        Combine text from multiple pages into single document.
        
        Args:
            page_texts: List of text strings from each page
        
        Returns:
            Combined text with page separators
        """
        combined_text = "\n\n--- PAGE BREAK ---\n\n".join(page_texts)
        logger.info(f"Merged {len(page_texts)} pages into combined text ({len(combined_text)} chars)")
        return combined_text
    
    def _parse_ocr_result(self, result: List) -> str:
        """
        Parse PaddleOCR result into plain text.
        
        PaddleOCR returns: [[[bbox], (text, confidence)], ...]
        
        Args:
            result: Raw OCR result from PaddleOCR
        
        Returns:
            Plain text string
        """
        if not result or result[0] is None:
            return ""
        
        text_lines = []
        
        try:
            for line in result[0]:
                if len(line) >= 2:
                    # line[1] is tuple: (text, confidence)
                    text = line[1][0]
                    text_lines.append(text)
        except Exception as e:
            logger.warning(f"Error parsing OCR result: {str(e)}")
        
        return "\n".join(text_lines)
    
    def extract_with_confidence(self, image: Union[Image.Image, np.ndarray]) -> List[dict]:
        """
        Extract text with confidence scores and bounding boxes.
        
        Args:
            image: PIL Image or numpy array
        
        Returns:
            List of dicts with 'text', 'confidence', 'bbox'
        """
        try:
            if isinstance(image, Image.Image):
                img_array = np.array(image)
            else:
                img_array = image
            
            result = self.ocr.ocr(img_array, cls=True)
            
            if not result or result[0] is None:
                return []
            
            extracted_data = []
            for line in result[0]:
                if len(line) >= 2:
                    bbox = line[0]
                    text, confidence = line[1]
                    
                    extracted_data.append({
                        "text": text,
                        "confidence": float(confidence),
                        "bbox": bbox
                    })
            
            return extracted_data
            
        except Exception as e:
            logger.error(f"OCR with confidence failed: {str(e)}")
            return []


class OCREngineFallback:
    """
    Fallback OCR engine if PaddleOCR is not available.
    Uses pytesseract as backup.
    """
    
    def __init__(self, tesseract_cmd: str = None):
        """
        Initialize Tesseract fallback engine.
        
        Args:
            tesseract_cmd: Path to tesseract executable (optional)
        """
        try:
            import pytesseract
            self.pytesseract = pytesseract
            
            if tesseract_cmd:
                self.pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            
            logger.warning("Using Tesseract fallback (PaddleOCR recommended for better accuracy)")
        except ImportError:
            raise ImportError("Neither PaddleOCR nor pytesseract is available")
    
    def extract_text_from_image(self, image: Union[Image.Image, np.ndarray]) -> str:
        """Extract text using Tesseract."""
        try:
            if isinstance(image, np.ndarray):
                image = Image.fromarray(image)
            
            text = self.pytesseract.image_to_string(image)
            return text
        except Exception as e:
            logger.error(f"Tesseract extraction failed: {str(e)}")
            return ""
    
    def extract_text_from_images(self, images: List[Union[Image.Image, np.ndarray]]) -> List[str]:
        """Extract text from multiple images."""
        return [self.extract_text_from_image(img) for img in images]
    
    def merge_page_texts(self, page_texts: List[str]) -> str:
        """Merge page texts."""
        return "\n\n--- PAGE BREAK ---\n\n".join(page_texts)
