# Production Invoice Extraction Engine

## 🚀 Overview

Production-grade multi-page invoice to JSON extraction system built with:
- **FastAPI** - High-performance REST API
- **PaddleOCR** - State-of-the-art OCR engine
- **Google Gemini** - LLM-powered extraction with retry logic
- **Universal Schema** - Constant JSON output format

## ✨ Features

✅ Multi-page PDF support
✅ High-accuracy OCR with PaddleOCR
✅ Intelligent extraction with Gemini 1.5 Flash
✅ Automatic retry with exponential backoff
✅ Fallback to rule-based extraction
✅ Always returns valid schema JSON
✅ Barcode detection support
✅ Processing metadata for debugging

## 📋 Requirements

- Python 3.8+
- Poppler (for PDF processing)
- Google Gemini API key

## 🔧 Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Poppler (Windows)

Download from: https://github.com/oschwartz10612/poppler-windows/releases

Extract to: `C:\Program Files\poppler-25.12.0\`

### 3. Set Environment Variables

Create a `.env` file:

```env
GEMINI_API_KEY=your_gemini_api_key_here
POPPLER_PATH=C:\Program Files\poppler-25.12.0\Library\bin
HOST=0.0.0.0
PORT=8000
DEBUG=false
```

## 🚀 Running the Server

### Development Mode

```bash
python main.py
```

### Production Mode

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

## 📡 API Endpoints

### 1. Health Check

```http
GET /
```

Returns service status and component health.

### 2. Get Schema

```http
GET /schema
```

Returns the universal invoice schema.

### 3. Extract Invoice

```http
POST /extract-invoice
Content-Type: multipart/form-data

file: <PDF file>
```

**Response:**
```json
{
  "header": {
    "vendor_details": {...},
    "invoice_details": {...},
    "customer_details": {...}
  },
  "document_type": "invoice",
  "company": {...},
  "bill_to": {...},
  "ship_to": {...},
  "line_items": [...],
  "summary": {...},
  "payment_instructions": {...},
  "codes": [...],
  "footer": {...},
  "_meta": {
    "ocr_pages": 3,
    "gemini_status": "success",
    "processing_time": 12.5,
    "warnings": [],
    "barcode_detected": false
  }
}
```

### 4. Batch Extraction

```http
POST /extract-invoice-batch
Content-Type: multipart/form-data

files: [<PDF file 1>, <PDF file 2>, ...]
```

## 🏗️ Architecture

```
PDF Upload
    ↓
PDF Processor (pdf2image)
    ↓
OCR Engine (PaddleOCR)
    ↓
Text Merging
    ↓
Gemini Client (with retry)
    ↓
Invoice Mapper
    ↓
Schema Validation
    ↓
JSON Response
```

## 📦 Project Structure

```
invoice_engine/
├── pdf_processor.py         # PDF to images conversion
├── ocr_engine_paddle.py     # PaddleOCR implementation
├── gemini_client.py         # Gemini API client with retry
├── schema_loader.py         # Schema management
├── invoice_mapper.py        # Data mapping and validation
├── universal_schema.json    # Constant output schema
├── barcode_extraction.py    # Barcode detection (optional)
└── ...

main.py                      # FastAPI application
requirements.txt             # Python dependencies
```

## 🛡️ Error Handling

The system implements robust error handling:

1. **PDF Conversion Failure**: Returns HTTP 500 with error details
2. **OCR Failure**: Continues with empty text, logs warning
3. **Gemini Failure**: 
   - Retries 3 times with exponential backoff (2s, 4s, 8s)
   - Falls back to empty schema
   - Never crashes
4. **Schema Mapping Failure**: Returns empty schema with defaults

## ⚙️ Configuration

### Environment Variables

- `GEMINI_API_KEY` - Google Gemini API key (required)
- `POPPLER_PATH` - Path to Poppler binaries (Windows)
- `HOST` - Server host (default: 0.0.0.0)
- `PORT` - Server port (default: 8000)
- `DEBUG` - Enable debug logging (default: false)

### OCR Engine

The system prefers PaddleOCR but falls back to Tesseract if unavailable.

To use GPU acceleration with PaddleOCR:
```bash
pip install paddlepaddle-gpu
```

Then edit `ocr_engine_paddle.py` and set `use_gpu=True`.

## 🧪 Testing

### Test with cURL

```bash
curl -X POST "http://localhost:8000/extract-invoice" \
  -F "file=@invoice.pdf" \
  -o result.json
```

### Test with Python

```python
import requests

url = "http://localhost:8000/extract-invoice"
files = {"file": open("invoice.pdf", "rb")}
response = requests.post(url, files=files)
result = response.json()

print(f"Invoice Number: {result['header']['invoice_details']['invoice_number']}")
print(f"Total Amount: {result['summary']['total_amount']}")
```

## 📊 Performance

**Typical Processing Times:**
- Single page invoice: 5-8 seconds
- Multi-page invoice (3 pages): 10-15 seconds

**Factors affecting speed:**
- Number of pages
- Image quality
- Network latency to Gemini API

## 🔒 Production Deployment

### Docker Deployment

```dockerfile
FROM python:3.10-slim

RUN apt-get update && apt-get install -y \
    poppler-utils \
    libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Render.com Deployment

Use the included `render.yaml` configuration.

## 🐛 Troubleshooting

### PaddleOCR Not Available

If PaddleOCR fails to install, the system will fallback to Tesseract.

Install Tesseract manually:
- Windows: https://github.com/UB-Mannheim/tesseract/wiki
- Linux: `sudo apt-get install tesseract-ocr`

### Gemini API Errors

- **429 Rate Limit**: System retries automatically
- **500 Server Error**: System retries automatically
- **Invalid API Key**: Check `GEMINI_API_KEY` environment variable

### Poppler Not Found

Ensure `POPPLER_PATH` points to the correct directory containing `pdftoppm.exe`.

## 📝 Schema Contract

The system **always** returns JSON matching the universal schema in `universal_schema.json`.

**Guarantees:**
- All fields are present
- Missing values are `null` (numbers) or `""` (strings)  
- No extra fields (except `_meta`)
- Structure never changes

## 🤝 Contributing

When adding features:
1. Never modify the universal schema structure
2. Always return schema-compliant JSON
3. Add comprehensive error handling
4. Update documentation

## 📄 License

Proprietary - Reno Infomatics

## 🔗 Links

- FastAPI: https://fastapi.tiangolo.com/
- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
- Google Gemini: https://ai.google.dev/
