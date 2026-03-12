from fastapi import FastAPI, Request, File, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from typing import Optional
import json
import os
import glob
import logging
import traceback
from datetime import datetime
import tempfile
from io import BytesIO
import asyncio
import time
import uuid
from typing import Dict, Any

# Load .env file into environment
env_path = os.path.join(os.getcwd(), ".env")
if os.path.exists(env_path):
    try:
        with open(env_path, "r", encoding="utf-8") as _ef:
            for ln in _ef:
                ln = ln.strip()
                if not ln or ln.startswith("#"):
                    continue
                if "=" not in ln:
                    continue
                k, v = ln.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and not os.getenv(k):
                    os.environ[k] = v
    except Exception:
        pass

app = FastAPI(
    title="Invoice OCR API",
    description="AI-powered invoice processing with Gemini & Tesseract OCR",
    version="1.0.0"
)

# Configure basic logging (can be controlled with DEBUG env var)
debug_mode = bool(os.getenv("DEBUG"))
log_level = logging.DEBUG if debug_mode else logging.INFO
logging.basicConfig(level=log_level, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Enable CORS for Postman and web clients
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

RUNS_DIR = os.path.join(os.getcwd(), "runs")
HISTORY_FILE = os.path.join(RUNS_DIR, "history.json")

# In-memory job registry for async processing (small scale)
JOBS: Dict[str, Any] = {}



@app.get('/')
def hello_json():
    """Return a simple JSON message for quick checks."""
    return {"message": "Hello world"}


@app.post('/ocr')
async def process_ocr(file: UploadFile = File(...), prefer_gemini: Optional[bool] = True):
    """
    Upload an invoice PDF or image and extract structured JSON via OCR.
    Returns extracted invoice data as JSON.
    
    NEW: Production-ready with smart PDF type detection and dual extraction pipeline.
    - Detects digital vs scanned PDFs automatically
    - Uses text extraction for digital PDFs (faster, cheaper)
    - Uses vision extraction for scanned PDFs
    - Prevents Gemini timeout with smart page selection
    - Safe barcode extraction (graceful fallback if libraries missing)
    - EasyOCR + pytesseract fallbacks
    
    Note: Processing may take up to 3 minutes for complex multi-page PDFs.
    """
    tmp_path = None
    print(f"\n{'='*70}")
    print(f"[API] New OCR request received")
    print(f"{'='*70}")
    
    try:
        start_time = time.time()
        print(f"\n[OCR] Processing file: {file.filename}")
        
        # Import processing modules
        from invoice_engine.barcode_extraction import extract_codes_from_images
        from invoice_engine.local_extraction import local_extract_invoice
        from invoice_engine.multipage_parser import parse_multipage_invoice
        from invoice_engine.pdf_detector import (
            detect_pdf_type, 
            extract_text_from_digital_pdf,
            convert_pdf_to_images,
            get_extraction_strategy
        )
        from invoice_engine.vision_llm_gemini import (
            extract_invoice_with_gemini,
            extract_invoice_from_text
        )
        
        # Save uploaded file to temp location
        suffix = os.path.splitext(file.filename)[1] if file.filename else ".tmp"
        print(f"[OCR] File type: {suffix}")
        
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name
        
        # Initialize metadata
        meta = {
            "gemini_attempted": False,
            "gemini_status": None,
            "gemini_error": None,
            "extraction_method": None,
            "pdf_type": None
        }
        result_json = None
        codes = []
        page_bytes_list = None
        
        # Handle PDF files with smart strategy
        if suffix.lower() == ".pdf":
            print("[OCR] PDF detected - analyzing type...")
            
            # Detect PDF type and get extraction strategy
            pdf_type, strategy = get_extraction_strategy(tmp_path)
            meta["pdf_type"] = pdf_type
            meta["extraction_strategy"] = strategy["method"]
            
            print(f"[OCR] PDF Type: {pdf_type}, Strategy: {strategy['method']}")
            
            if strategy["method"] == "text" and strategy["use_text_extraction"]:
                # Digital PDF: Extract text directly
                print("[OCR] Digital PDF detected - extracting text...")
                text_content = extract_text_from_digital_pdf(tmp_path)
                
                if text_content and prefer_gemini and os.getenv("GEMINI_API_KEY"):
                    print("[OCR] Sending text to Gemini...")
                    meta["gemini_attempted"] = True
                    meta["extraction_method"] = "text_to_gemini"
                    
                    try:
                        result_json = await asyncio.wait_for(
                            asyncio.to_thread(extract_invoice_from_text, text_content, timeout=180),
                            timeout=200
                        )
                        meta["gemini_status"] = "success"
                        print("[OCR] ✓ Gemini text extraction successful")
                    except asyncio.TimeoutError:
                        print("[OCR] Gemini text extraction timed out")
                        meta["gemini_status"] = "timeout"
                        result_json = None
                    except Exception as e:
                        print(f"[OCR] Gemini text extraction failed: {e}")
                        meta["gemini_error"] = str(e)
                        meta["gemini_status"] = "error"
                        result_json = None
                else:
                    print("[OCR] Using local extraction for digital PDF")
                    meta["extraction_method"] = "local_text"
            
            elif strategy["method"] == "vision" and strategy["convert_to_images"]:
                # Scanned PDF: Convert to images with smart page selection
                print(f"[OCR] Scanned PDF detected - converting to images (max {strategy['max_pages']} pages, DPI={strategy['dpi']})...")
                
                try:
                    page_bytes_list = await asyncio.wait_for(
                        asyncio.to_thread(
                            convert_pdf_to_images,
                            tmp_path,
                            max_pages=strategy["max_pages"],
                            dpi=strategy["dpi"],
                            include_last_page=True
                        ),
                        timeout=90
                    )
                except asyncio.TimeoutError:
                    print("[OCR] PDF conversion timed out")
                    return JSONResponse(
                        status_code=504,
                        content={"status": "ERROR", "error": "PDF conversion timed out"}
                    )
                except Exception as e:
                    print(f"[OCR] PDF conversion failed: {e}")
                    return JSONResponse(
                        status_code=400,
                        content={"status": "ERROR", "error": "PDF conversion failed", "detail": str(e)}
                    )
                
                if page_bytes_list:
                    image_bytes = page_bytes_list[0]
                    meta["extraction_method"] = "vision"
                else:
                    return JSONResponse(
                        status_code=400,
                        content={"status": "ERROR", "error": "No pages extracted from PDF"}
                    )
        else:
            # Regular image file
            print("[OCR] Image file detected")
            with open(tmp_path, "rb") as imgf:
                image_bytes = imgf.read()
            meta["extraction_method"] = "vision"
        
        # Extract barcodes (safe - won't crash if libraries missing)
        print("[OCR] Extracting barcodes/QR codes...")
        try:
            try:
                if page_bytes_list:
                    codes = await asyncio.wait_for(
                        asyncio.to_thread(extract_codes_from_images, page_bytes_list),
                        timeout=15
                    )
                else:
                    codes = await asyncio.wait_for(
                        asyncio.to_thread(extract_codes_from_images, [image_bytes]),
                        timeout=15
                    )
                print(f"[OCR] Found {len(codes)} barcode(s)")
            except asyncio.TimeoutError:
                print("[OCR] Barcode extraction timed out")
                codes = []
        except Exception as e:
            print(f"[OCR] Barcode extraction failed: {e}")
            codes = []
        
        # Try Gemini vision extraction if not already done
        if result_json is None and meta["extraction_method"] == "vision":
            if prefer_gemini and os.getenv("GEMINI_API_KEY"):
                print("[OCR] Attempting Gemini vision extraction...")
                meta["gemini_attempted"] = True
                
                try:
                    gemini_images = page_bytes_list if page_bytes_list else [image_bytes]
                    
                    result_json = await asyncio.wait_for(
                        asyncio.to_thread(extract_invoice_with_gemini, gemini_images, timeout=180),
                        timeout=200
                    )
                    
                    if isinstance(result_json, dict):
                        if result_json.get("status") == "NEEDS_REVIEW":
                            print("[OCR] Gemini returned NEEDS_REVIEW")
                            meta["gemini_status"] = "needs_review"
                            # Store Gemini debug info
                            if "_gemini_diagnostics" in result_json:
                                meta["gemini_diagnostics"] = result_json["_gemini_diagnostics"]
                            result_json = None  # Fall back to local OCR
                        else:
                            print("[OCR] ✓ Gemini vision extraction successful")
                            meta["gemini_status"] = "success"
                    
                except asyncio.TimeoutError:
                    print("[OCR] Gemini vision extraction timed out")
                    meta["gemini_status"] = "timeout"
                    result_json = None
                except Exception as e:
                    print(f"[OCR] Gemini vision extraction failed: {e}")
                    meta["gemini_error"] = str(e)
                    meta["gemini_status"] = "error"
                    result_json = None
        
        # Fallback to local OCR if needed
        if result_json is None:
            print("[OCR] Using local OCR extraction...")
            meta["local_ocr_used"] = True
            
            try:
                if page_bytes_list and len(page_bytes_list) > 1:
                    print(f"[OCR] Multi-page PDF ({len(page_bytes_list)} pages)")
                    try:
                        result_json = await asyncio.wait_for(
                            asyncio.to_thread(parse_multipage_invoice, tmp_path),
                            timeout=120
                        )
                    except asyncio.TimeoutError:
                        print("[OCR] Multi-page parsing timed out")
                        result_json = {
                            "status": "NEEDS_REVIEW",
                            "error": "Multi-page parsing timed out"
                        }
                else:
                    print("[OCR] Single page extraction")
                    try:
                        result_json = await asyncio.wait_for(
                            asyncio.to_thread(local_extract_invoice, image_bytes, "eng"),
                            timeout=120
                        )
                    except asyncio.TimeoutError:
                        print("[OCR] Local extraction timed out")
                        result_json = {
                            "status": "NEEDS_REVIEW",
                            "error": "Local extraction timed out"
                        }
                
                print("[OCR] ✓ Local extraction complete")
                
            except Exception as e:
                print(f"[OCR] Local extraction failed: {e}")
                result_json = {
                    "status": "NEEDS_REVIEW",
                    "error": f"Local extraction failed: {str(e)}"
                }
        
        # Ensure result is properly formatted
        if isinstance(result_json, str):
            try:
                result_json = json.loads(result_json)
            except Exception:
                result_json = {
                    "status": "NEEDS_REVIEW",
                    "error": "Invalid JSON response",
                    "raw_text": result_json
                }
        
        if not isinstance(result_json, dict):
            result_json = {
                "status": "NEEDS_REVIEW",
                "error": "Invalid response format",
                "raw_response": str(result_json)
            }
        
        # Add codes and metadata
        result_json["codes"] = codes
        result_json["_meta"] = meta
        
        total_time = time.time() - start_time
        print(f"[OCR] ✓ Total processing time: {total_time:.2f}s")
        print(f"{'='*70}\n")
        
        return JSONResponse(content=result_json)
    
    except Exception as e:
        tb = traceback.format_exc()
        logger.exception("OCR processing failed")
        print(f"[OCR] ✗ Fatal error: {e}")
        print(f"{'='*70}\n")
        
        content = {
            "status": "ERROR",
            "error": "Processing failed",
            "detail": str(e)
        }
        if debug_mode:
            content["traceback"] = tb
        
        return JSONResponse(status_code=500, content=content)
    
    finally:
        # Cleanup temp file
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


@app.get("/health")
def health():
    runs_writable = os.path.isdir(RUNS_DIR) and os.access(RUNS_DIR, os.W_OK)
    return {"status": "ok" if runs_writable else "degraded", "runs_dir_writable": runs_writable, "timestamp": datetime.utcnow().isoformat() + "Z"}


@app.post('/ocr_async')
async def process_ocr_async(file: UploadFile = File(...)):
    """Accept file and return immediately with a job id; processing happens in background."""
    try:
        content = await file.read()
        suffix = os.path.splitext(file.filename)[1] if file.filename else ".tmp"
        # Persist uploaded bytes to a temp file which the background worker will remove
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        job_id = uuid.uuid4().hex
        JOBS[job_id] = {"status": "queued", "created": datetime.utcnow().isoformat()}

        # Schedule background processing
        asyncio.create_task(_background_ocr_job(tmp_path, file.filename or f"upload{suffix}", job_id))

        return JSONResponse({"job_id": job_id, "status": "queued"})
    except Exception as e:
        logger.exception("Failed to enqueue async OCR job")
        return JSONResponse(status_code=500, content={"status": "error", "error": str(e)})


async def _background_ocr_job(tmp_path: str, filename: str, job_id: str):
    """Background wrapper that calls the existing `process_ocr` handler and stores the result."""
    try:
        JOBS[job_id]["status"] = "running"
        # Create a Starlette UploadFile from the temp file bytes and call the regular handler
        from starlette.datastructures import UploadFile as StarletteUploadFile

        with open(tmp_path, 'rb') as f:
            data = f.read()

        bio = BytesIO()
        bio.write(data)
        bio.seek(0)

        upload = StarletteUploadFile(bio, filename=filename)

        # Call the existing endpoint function directly
        resp = await process_ocr(upload)

        # Extract JSON content from JSONResponse
        if hasattr(resp, 'body') and resp.body:
            try:
                result = json.loads(resp.body.decode())
            except Exception:
                result = {"status": "ERROR_PARSING_RESPONSE", "raw": resp.body.decode(errors='ignore')}
        else:
            result = {"status": "UNKNOWN_RESPONSE", "detail": str(resp)}

        JOBS[job_id]["status"] = "done"
        JOBS[job_id]["completed"] = datetime.utcnow().isoformat()
        JOBS[job_id]["result"] = result

        # Save result to runs dir for persistence
        try:
            os.makedirs(RUNS_DIR, exist_ok=True)
            with open(os.path.join(RUNS_DIR, f"{job_id}.json"), 'w', encoding='utf-8') as rf:
                json.dump(result, rf)
        except Exception:
            logger.exception("Failed to persist async OCR result")

    except Exception as e:
        logger.exception("Background OCR job failed")
        JOBS[job_id]["status"] = "error"
        JOBS[job_id]["error"] = str(e)
    finally:
        try:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


@app.get('/ocr_status/{job_id}')
def ocr_status(job_id: str):
    entry = JOBS.get(job_id)
    if not entry:
        return JSONResponse(status_code=404, content={"status": "not_found"})
    return JSONResponse(content={"job_id": job_id, "status": entry.get("status"), "created": entry.get("created"), "completed": entry.get("completed", None)})


@app.get('/ocr_result/{job_id}')
def ocr_result(job_id: str):
    entry = JOBS.get(job_id)
    if not entry:
        # try loading from disk
        path = os.path.join(RUNS_DIR, f"{job_id}.json")
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as rf:
                    data = json.load(rf)
                return JSONResponse(content={"job_id": job_id, "status": "done", "result": data})
            except Exception:
                return JSONResponse(status_code=500, content={"status": "error", "error": "failed_to_read_result"})
        return JSONResponse(status_code=404, content={"status": "not_found"})

    if entry.get("status") == "done":
        return JSONResponse(content={"job_id": job_id, "status": "done", "result": entry.get("result")})
    elif entry.get("status") == "error":
        return JSONResponse(status_code=500, content={"job_id": job_id, "status": "error", "error": entry.get("error")})
    else:
        return JSONResponse(content={"job_id": job_id, "status": entry.get("status")})


if __name__ == "__main__":
    try:
        import uvicorn
        host = os.getenv("HOST", "0.0.0.0")
        port = int(os.getenv("PORT", str(8070)))
        logger.info(f"Starting server on {host}:{port}")
        uvicorn.run(app, host=host, port=port)
    except Exception:
        logger.exception("Failed to start uvicorn. Run with: uvicorn app:app --host 0.0.0.0 --port 8070 --reload")
