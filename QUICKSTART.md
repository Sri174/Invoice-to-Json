# 🚀 Quick Start Guide

## Installation (5 minutes)

### Step 1: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 2: Install Poppler (Windows)

1. Download: https://github.com/oschwartz10612/poppler-windows/releases/latest
2. Extract to: `C:\Program Files\poppler-25.12.0\`

### Step 3: Set Up Environment

Create `.env` file:

```env
GEMINI_API_KEY=your_api_key_here
POPPLER_PATH=C:\Program Files\poppler-25.12.0\Library\bin
PORT=8000
```

Get your Gemini API key: https://ai.google.dev/

### Step 4: Test Installation

```bash
python test_system.py
```

### Step 5: Start Server

```bash
python main.py
```

Server will start at: http://localhost:8000

## 📝 Test the API

### Using Browser

Visit: http://localhost:8000

You should see:
```json
{
  "service": "Invoice Extraction Engine",
  "version": "2.0.0",
  "status": "running"
}
```

### Using cURL

```bash
curl -X POST "http://localhost:8000/extract-invoice" \
  -F "file=@your_invoice.pdf" \
  -o result.json
```

### Using Python

```python
import requests

url = "http://localhost:8000/extract-invoice"
files = {"file": open("invoice.pdf", "rb")}
response = requests.post(url, files=files)

print(response.json())
```

### Using Postman

1. Open Postman
2. Create POST request: `http://localhost:8000/extract-invoice`
3. Body → form-data
4. Key: `file` (type: File)
5. Value: Select your PDF
6. Send

## 🎯 Expected Response

```json
{
  "header": {
    "vendor_details": {...},
    "invoice_details": {
      "invoice_number": "INV-12345",
      "invoice_date": "2024-01-15",
      ...
    },
    ...
  },
  "line_items": [...],
  "summary": {
    "total_amount": 1500.00,
    ...
  },
  "_meta": {
    "ocr_pages": 2,
    "gemini_status": "success",
    "processing_time": 8.5
  }
}
```

## 🔧 Troubleshooting

### PaddleOCR Installation Issues

If PaddleOCR fails to install, the system will automatically use Tesseract as fallback.

To install Tesseract on Windows:
1. Download: https://github.com/UB-Mannheim/tesseract/wiki
2. Install to: `C:\Program Files\Tesseract-OCR`
3. Add to PATH

### Gemini API Errors

**Error: "GEMINI_API_KEY not found"**
- Solution: Add `GEMINI_API_KEY=your_key` to `.env` file

**Error: HTTP 429 (Rate Limit)**
- Solution: System retries automatically. If persistent, wait a few minutes.

**Error: HTTP 401 (Unauthorized)**
- Solution: Check your API key is valid at https://ai.google.dev/

### Poppler Not Found (Windows)

**Error: "Unable to get page count"**
- Solution: Set `POPPLER_PATH` in `.env` file to point to poppler bin folder

### Port Already in Use

**Error: "Address already in use"**
- Solution: Change PORT in `.env` or stop the other process

```bash
# Find process using port 8000
netstat -ano | findstr :8000

# Kill process (Windows)
taskkill /PID <process_id> /F
```

## 📊 Performance Tips

### For Faster Processing

1. **Use smaller DPI**: Edit `main.py` → change `dpi=300` to `dpi=200`
2. **Enable GPU**: Install `paddlepaddle-gpu` and set `use_gpu=True` in `ocr_engine_paddle.py`
3. **Increase workers**: Run with `--workers 4` for concurrent requests

### For Better Accuracy

1. **Use higher DPI**: Change to `dpi=400`
2. **Enable angle classification**: Already enabled by default
3. **Pre-process images**: Enhance contrast before uploading

## 🎓 Next Steps

- Read [PRODUCTION_README.md](PRODUCTION_README.md) for full documentation
- Check [universal_schema.json](invoice_engine/universal_schema.json) for schema details
- Explore API at http://localhost:8000/docs (FastAPI automatic docs)

## 💡 Tips

1. **Always check `_meta` field** for processing details
2. **Missing fields** will be `null` or `""` (never removed)
3. **Schema never changes** - safe to build integrations
4. **Retries are automatic** - no manual intervention needed
5. **OCR takes time** - expect 5-15 seconds per invoice

## 🆘 Need Help?

1. Run diagnostic: `python test_system.py`
2. Check logs in terminal
3. Verify `.env` configuration
4. Test with sample invoice first

## ✅ Success Checklist

- [ ] All tests pass in `test_system.py`
- [ ] Server starts without errors
- [ ] Can access http://localhost:8000
- [ ] Successfully extract a test invoice
- [ ] Response matches schema structure
- [ ] `_meta.gemini_status` shows "success"

---

**Ready to go? Start the server:**

```bash
python main.py
```

Then test with:

```bash
curl http://localhost:8000
```
