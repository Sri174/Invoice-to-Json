"""
pdf_processor.py
----------------
Converts PDF files into a list of page images for OCR processing.
Uses pdf2image library with poppler backend.
"""

import io
from typing import List, Union
from PIL import Image
from pdf2image import convert_from_bytes, convert_from_path
import logging

logger = logging.getLogger(__name__)


class PDFProcessor:
    """Handles PDF to image conversion for multi-page invoice processing."""
    
    def __init__(self, poppler_path: str = None):
        """
        Initialize PDF processor.
        
        Args:
            poppler_path: Optional path to poppler binaries (Windows).
                         If None, assumes poppler is in system PATH.
        """
        self.poppler_path = poppler_path
        logger.info(f"PDFProcessor initialized with poppler_path: {poppler_path}")
    
    def convert_pdf_to_images(
        self, 
        pdf_file: Union[bytes, str], 
        dpi: int = 300
    ) -> List[Image.Image]:
        """
        Convert PDF to list of PIL images (one per page).
        
        Args:
            pdf_file: Either bytes content or file path string
            dpi: Resolution for conversion (default 300)
        
        Returns:
            List of PIL Image objects, one per page
        
        Raises:
            Exception: If conversion fails
        """
        try:
            if isinstance(pdf_file, bytes):
                logger.info(f"Converting PDF from bytes ({len(pdf_file)} bytes) at {dpi} DPI")
                images = convert_from_bytes(
                    pdf_file,
                    dpi=dpi,
                    poppler_path=self.poppler_path
                )
            else:
                logger.info(f"Converting PDF from path: {pdf_file} at {dpi} DPI")
                images = convert_from_path(
                    pdf_file,
                    dpi=dpi,
                    poppler_path=self.poppler_path
                )
            
            logger.info(f"Successfully converted PDF to {len(images)} page(s)")
            return images
            
        except Exception as e:
            logger.error(f"PDF conversion failed: {str(e)}")
            raise Exception(f"Failed to convert PDF to images: {str(e)}")
    
    def convert_single_page(
        self, 
        pdf_file: Union[bytes, str], 
        page_number: int = 1,
        dpi: int = 300
    ) -> Image.Image:
        """
        Convert a single page from PDF to image.
        
        Args:
            pdf_file: Either bytes content or file path string
            page_number: Page to convert (1-indexed)
            dpi: Resolution for conversion
        
        Returns:
            PIL Image object for the specified page
        """
        try:
            if isinstance(pdf_file, bytes):
                images = convert_from_bytes(
                    pdf_file,
                    dpi=dpi,
                    first_page=page_number,
                    last_page=page_number,
                    poppler_path=self.poppler_path
                )
            else:
                images = convert_from_path(
                    pdf_file,
                    dpi=dpi,
                    first_page=page_number,
                    last_page=page_number,
                    poppler_path=self.poppler_path
                )
            
            if not images:
                raise Exception(f"No image generated for page {page_number}")
            
            logger.info(f"Successfully converted page {page_number}")
            return images[0]
            
        except Exception as e:
            logger.error(f"Single page conversion failed: {str(e)}")
            raise Exception(f"Failed to convert page {page_number}: {str(e)}")
    
    def get_page_count(self, pdf_file: Union[bytes, str]) -> int:
        """
        Get the number of pages in a PDF without full conversion.
        
        Args:
            pdf_file: Either bytes content or file path string
        
        Returns:
            Number of pages in the PDF
        """
        try:
            # Quick conversion at low DPI just to count pages
            if isinstance(pdf_file, bytes):
                images = convert_from_bytes(
                    pdf_file,
                    dpi=72,  # Low DPI for speed
                    poppler_path=self.poppler_path
                )
            else:
                images = convert_from_path(
                    pdf_file,
                    dpi=72,
                    poppler_path=self.poppler_path
                )
            
            page_count = len(images)
            logger.info(f"PDF contains {page_count} page(s)")
            return page_count
            
        except Exception as e:
            logger.error(f"Failed to count PDF pages: {str(e)}")
            return 0
