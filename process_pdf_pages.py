"""
Multi-page PDF processor with per-page Gemini extraction.
Splits PDF into individual pages and processes each with Google Gemini API.
"""
import os
import json
import sys
from typing import List, Dict, Any
from google import genai
from google.genai import types
from pdf2image import convert_from_path
from PIL import Image
from io import BytesIO

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

# Configuration
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-1.5-flash"
OUTPUT_FILE = "final_output.json"

# Prompt template
PROMPT_TEMPLATE = """You are a document parsing system.
This input represents PAGE {page_number} of a multi-page document.

TASK:
- Extract ALL visible text, tables, and fields from this page image.
- Preserve original labels and values.
- If a value is missing, use null.
- Do NOT summarize.
- Do NOT infer data from other pages.
- Do NOT add explanations.

OUTPUT FORMAT:
Return STRICT JSON only.
No markdown.
No comments.
No extra text."""


def build_prompt(page_number: int) -> str:
    """Build the Gemini prompt for a single page."""
    return PROMPT_TEMPLATE.format(page_number=page_number)


def process_page_with_gemini(page_number: int, page_image: Image.Image, client) -> Dict[str, Any]:
    """Send a single page image to Gemini and parse JSON response."""
    prompt = build_prompt(page_number)
    
    try:
        # Convert image to bytes
        img_byte_arr = BytesIO()
        page_image.save(img_byte_arr, format='JPEG')
        img_byte_arr = img_byte_arr.getvalue()
        
        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=[
                prompt,
                types.Part.from_bytes(data=img_byte_arr, mime_type="image/jpeg")
            ],
            config=types.GenerateContentConfig(
                temperature=0.0,
                top_p=1.0,
                top_k=1,
                max_output_tokens=8192,
            )
        )
        
        raw_text = response.text.strip()
        
        # Remove markdown code blocks if present
        if raw_text.startswith("```json"):
            raw_text = raw_text[7:]
        if raw_text.startswith("```"):
            raw_text = raw_text[3:]
        if raw_text.endswith("```"):
            raw_text = raw_text[:-3]
        raw_text = raw_text.strip()
        
        # Parse JSON
        try:
            parsed = json.loads(raw_text)
            return {"page": page_number, "status": "success", "data": parsed}
        except json.JSONDecodeError as e:
            return {"page": page_number, "status": "parse_error", "error": str(e), "raw": raw_text}
    
    except Exception as e:
        return {"page": page_number, "status": "extraction_error", "error": str(e)}


def process_pdf(pdf_path: str) -> List[Dict[str, Any]]:
    """Process all pages of a PDF and return list of page results."""
    if not GEMINI_API_KEY:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    
    client = genai.Client(api_key=GEMINI_API_KEY)
    
    # Convert PDF pages to images
    print("Converting PDF to images...")
    try:
        images = convert_from_path(pdf_path, dpi=200)
    except Exception as e:
        raise RuntimeError(f"Failed to convert PDF to images: {e}")
    
    total_pages = len(images)
    print(f"Processing {total_pages} pages from: {pdf_path}")
    
    results = []
    
    for page_num, page_image in enumerate(images):
        page_number = page_num + 1
        
        print(f"Processing page {page_number}/{total_pages}...")
        
        result = process_page_with_gemini(page_number, page_image, client)
        results.append(result)
        
        if result["status"] == "success":
            print(f"  ✓ Page {page_number} processed successfully")
        else:
            print(f"  ✗ Page {page_number} failed: {result.get('status')}")
    
    return results


def merge_results(page_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge all page-level results into a single JSON structure."""
    merged = {
        "document": {
            "total_pages": len(page_results),
            "processed_pages": sum(1 for r in page_results if r.get("status") == "success"),
            "failed_pages": sum(1 for r in page_results if r.get("status") != "success")
        },
        "pages": page_results
    }
    return merged


def main():
    if len(sys.argv) < 2:
        print("Usage: python process_pdf_pages.py <pdf_file>")
        sys.exit(1)
    
    pdf_path = sys.argv[1]
    
    if not os.path.exists(pdf_path):
        print(f"Error: File not found: {pdf_path}")
        sys.exit(1)
    
    print("=" * 70)
    print("Multi-page PDF Processor with Gemini API")
    print("=" * 70)
    
    try:
        page_results = process_pdf(pdf_path)
        final_output = merge_results(page_results)
        
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            json.dump(final_output, f, indent=2, ensure_ascii=False)
        
        print("\n" + "=" * 70)
        print(f"✓ Processing complete")
        print(f"✓ Output saved to: {OUTPUT_FILE}")
        print(f"✓ Total pages: {final_output['document']['total_pages']}")
        print(f"✓ Successfully processed: {final_output['document']['processed_pages']}")
        print("=" * 70)
    
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
