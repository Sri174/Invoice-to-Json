"""
main.py
-------
Production-grade FastAPI application for multi-page invoice extraction.
Always returns JSON matching the constant universal schema.
"""

import os
import io
import time
import logging
import platform
from datetime import datetime
from typing import Optional
import traceback

from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Invoice engine modules
from invoice_engine.pdf_processor import PDFProcessor
from invoice_engine.ocr_engine_paddle import OCREngine, OCREngineFallback, PADDLEOCR_AVAILABLE
from invoice_engine.gemini_client import GeminiClient
from invoice_engine.schema_loader import get_universal_schema
from invoice_engine.invoice_mapper import InvoiceMapper

# Optional: Barcode detection
try:
    from invoice_engine.barcode_extraction import detect_barcodes
    BARCODE_AVAILABLE = True
except ImportError:
    BARCODE_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Invoice Extraction Engine",
    description="Production-grade multi-page invoice to JSON extraction system",
    version="2.0.0"
)

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global components (initialized on startup)
pdf_processor: Optional[PDFProcessor] = None
ocr_engine: Optional[OCREngine] = None
gemini_client: Optional[GeminiClient] = None
invoice_mapper: Optional[InvoiceMapper] = None


@app.on_event("startup")
async def startup_event():
    """Initialize components on application startup."""
    global pdf_processor, ocr_engine, gemini_client, invoice_mapper
    
    logger.info("=== Invoice Extraction Engine Starting ===")
    
    try:
        # Initialize PDF Processor
        # On Windows: use POPPLER_PATH or default Windows location
        # On Linux/Docker: use system poppler (installed via apt-get)
        if platform.system() == "Windows":
            poppler_path = os.getenv("POPPLER_PATH", r"C:\Program Files\poppler-25.12.0\Library\bin")
        else:
            poppler_path = os.getenv("POPPLER_PATH")  # None = use system PATH
        
        pdf_processor = PDFProcessor(poppler_path=poppler_path)
        logger.info(f"✓ PDF Processor initialized (poppler_path: {poppler_path or 'system PATH'})")
        
        # Initialize OCR Engine
        if PADDLEOCR_AVAILABLE:
            try:
                ocr_engine = OCREngine(use_angle_cls=True, lang="en")
                logger.info("✓ PaddleOCR engine initialized")
            except Exception as e:
                logger.warning(f"PaddleOCR initialization failed, trying fallback: {str(e)}")
                ocr_engine = OCREngineFallback()
                logger.info("✓ Tesseract fallback engine initialized")
        else:
            ocr_engine = OCREngineFallback()
            logger.info("✓ Tesseract fallback engine initialized")
        
        # Initialize Gemini Client
        gemini_client = GeminiClient(
            model="gemini-1.5-flash",
            max_retries=3,
            timeout=90
        )
        logger.info("✓ Gemini client initialized")
        
        # Test Gemini connection
        if gemini_client.test_connection():
            logger.info("✓ Gemini API connection verified")
        else:
            logger.warning("⚠ Gemini API connection test failed (will retry on requests)")
        
        # Initialize Invoice Mapper
        invoice_mapper = InvoiceMapper()
        logger.info("✓ Invoice mapper initialized")
        
        logger.info("=== All components initialized successfully ===")
        
    except Exception as e:
        logger.error(f"Startup initialization failed: {str(e)}")
        logger.error(traceback.format_exc())
        raise


@app.get("/")
async def root():
    """Health check endpoint."""
    return {
        "service": "Invoice Extraction Engine",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "pdf_processor": pdf_processor is not None,
            "ocr_engine": ocr_engine is not None,
            "gemini_client": gemini_client is not None,
            "invoice_mapper": invoice_mapper is not None,
            "paddleocr": PADDLEOCR_AVAILABLE,
            "barcode": BARCODE_AVAILABLE
        }
    }


@app.get("/schema")
async def get_schema():
    """Get the universal invoice schema."""
    return get_universal_schema()


@app.post("/extract-invoice")
async def extract_invoice(file: UploadFile = File(...)):
    """
    Extract invoice data from uploaded PDF file.
    
    Returns JSON that always matches the universal schema.
    
    Args:
        file: PDF file (multipart/form-data)
    
    Returns:
        JSON response with extracted invoice data and metadata
    """
    start_time = time.time()
    
    # Metadata for debugging
    meta = {
        "ocr_pages": 0,
        "gemini_status": "not_attempted",
        "processing_time": 0,
        "warnings": [],
        "barcode_detected": False
    }
    
    try:
        logger.info(f"=== Processing invoice: {file.filename} ===")
        
        # Validate file type
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(
                status_code=400, 
                detail="Only PDF files are supported"
            )
        
        # Read PDF file
        pdf_bytes = await file.read()
        logger.info(f"Read PDF file: {len(pdf_bytes)} bytes")
        
        # Step 1: Convert PDF to images
        logger.info("Step 1: Converting PDF to images...")
        try:
            page_images = pdf_processor.convert_pdf_to_images(pdf_bytes, dpi=300)
            meta["ocr_pages"] = len(page_images)
            logger.info(f"Converted to {len(page_images)} page(s)")
        except Exception as e:
            logger.error(f"PDF conversion failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Failed to convert PDF: {str(e)}"
            )
        
        # Step 2: OCR each page
        logger.info("Step 2: Running OCR on pages...")
        try:
            page_texts = ocr_engine.extract_text_from_images(page_images)
            logger.info(f"Extracted text from {len(page_texts)} page(s)")
        except Exception as e:
            logger.error(f"OCR extraction failed: {str(e)}")
            meta["warnings"].append(f"OCR failed: {str(e)}")
            page_texts = [""]
        
        # Step 3: Merge page texts
        logger.info("Step 3: Merging page texts...")
        combined_text = ocr_engine.merge_page_texts(page_texts)
        logger.info(f"Combined text length: {len(combined_text)} characters")
        
        if len(combined_text) < 50:
            meta["warnings"].append("Very little text extracted from document")
        
        # Step 4: Optional barcode detection
        if BARCODE_AVAILABLE:
            try:
                barcodes = detect_barcodes(page_images[0])  # Check first page
                if barcodes:
                    meta["barcode_detected"] = True
                    logger.info(f"Detected {len(barcodes)} barcode(s)")
            except Exception as e:
                logger.warning(f"Barcode detection failed: {str(e)}")
        
        # Step 5: Extract using Gemini
        logger.info("Step 4: Calling Gemini for extraction...")
        extracted_data = None
        
        try:
            schema = get_universal_schema()
            extracted_data = gemini_client.extract_invoice(combined_text, schema)
            meta["gemini_status"] = "success"
            logger.info("Gemini extraction successful")
            
        except Exception as e:
            logger.error(f"Gemini extraction failed: {str(e)}")
            meta["gemini_status"] = "failed"
            meta["warnings"].append(f"Gemini failed: {str(e)}")
            
            # Fallback: return empty schema
            logger.info("Using fallback: returning empty schema")
            extracted_data = get_universal_schema()
        
        # Step 6: Map to schema
        logger.info("Step 5: Mapping to universal schema...")
        try:
            result = invoice_mapper.map_to_schema(extracted_data)
            
            # Ensure required fields
            result = invoice_mapper.ensure_required_fields(result)
            
            # Remove any extra fields
            result = invoice_mapper.remove_extra_fields(result)
            
            logger.info("Schema mapping completed")
            
        except Exception as e:
            logger.error(f"Schema mapping failed: {str(e)}")
            meta["warnings"].append(f"Mapping failed: {str(e)}")
            result = get_universal_schema()
        
        # Add metadata
        meta["processing_time"] = round(time.time() - start_time, 2)
        result = invoice_mapper.add_metadata(result, meta)
        
        logger.info(f"=== Processing completed in {meta['processing_time']}s ===")
        
        return JSONResponse(content=result)
        
    except HTTPException:
        raise
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}")
        logger.error(traceback.format_exc())
        
        # Return empty schema with error metadata
        meta["processing_time"] = round(time.time() - start_time, 2)
        meta["warnings"].append(f"Critical error: {str(e)}")
        meta["gemini_status"] = "error"
        
        empty_result = get_universal_schema()
        empty_result = invoice_mapper.add_metadata(empty_result, meta)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal processing error",
                "detail": str(e),
                "result": empty_result
            }
        )


@app.post("/extract-invoice-batch")
async def extract_invoice_batch(files: list[UploadFile] = File(...)):
    """
    Extract invoice data from multiple PDF files.
    
    Args:
        files: List of PDF files
    
    Returns:
        List of extraction results
    """
    results = []
    
    for file in files:
        try:
            result = await extract_invoice(file)
            results.append({
                "filename": file.filename,
                "success": True,
                "data": result
            })
        except Exception as e:
            results.append({
                "filename": file.filename,
                "success": False,
                "error": str(e)
            })
    
    return {"results": results}


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "components": {
            "pdf_processor": pdf_processor is not None,
            "ocr_engine": ocr_engine is not None,
            "gemini_client": gemini_client is not None,
            "invoice_mapper": invoice_mapper is not None
        }
    }


if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", 8000))
    
    logger.info(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=True,
        log_level="info"
    )
