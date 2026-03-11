# 📡 API Documentation

## Base URL

```
http://localhost:8000
```

---

## Endpoints

### 1. Health Check

Get service status and version.

**Endpoint:** `GET /`

**Request:**
```bash
curl http://localhost:8000/
```

**Response:**
```json
{
  "service": "Invoice Extraction Engine",
  "version": "2.0.0",
  "status": "running",
  "timestamp": "2024-01-15T10:30:00",
  "components": {
    "pdf_processor": true,
    "ocr_engine": true,
    "gemini_client": true,
    "invoice_mapper": true,
    "paddleocr": true,
    "barcode": true
  }
}
```

---

### 2. Get Universal Schema

Retrieve the constant invoice schema.

**Endpoint:** `GET /schema`

**Request:**
```bash
curl http://localhost:8000/schema
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
  "line_items": [{...}],
  "summary": {...},
  "payment_instructions": {...},
  "codes": [{...}],
  "footer": {...}
}
```

---

### 3. Extract Invoice (Main Endpoint)

Extract structured data from invoice PDF.

**Endpoint:** `POST /extract-invoice`

**Content-Type:** `multipart/form-data`

**Parameters:**
- `file` (required): PDF file

**Request (cURL):**
```bash
curl -X POST "http://localhost:8000/extract-invoice" \
  -H "Content-Type: multipart/form-data" \
  -F "file=@invoice.pdf" \
  -o result.json
```

**Request (Python):**
```python
import requests

url = "http://localhost:8000/extract-invoice"
files = {"file": open("invoice.pdf", "rb")}
response = requests.post(url, files=files)

data = response.json()
print(f"Invoice: {data['header']['invoice_details']['invoice_number']}")
print(f"Total: {data['summary']['total_amount']}")
```

**Request (JavaScript):**
```javascript
const formData = new FormData();
formData.append('file', fileInput.files[0]);

fetch('http://localhost:8000/extract-invoice', {
  method: 'POST',
  body: formData
})
.then(response => response.json())
.then(data => {
  console.log('Invoice Number:', data.header.invoice_details.invoice_number);
  console.log('Total:', data.summary.total_amount);
});
```

**Success Response (200):**
```json
{
  "header": {
    "vendor_details": {
      "company_name_en": "ABC Trading LLC",
      "company_name_ar": "شركة ABC",
      "address": "123 Business Street, Dubai",
      "contact_info": {
        "head_office_tel": "+971-4-1234567",
        "head_office_fax": "+971-4-1234568",
        "showroom_tel": "+971-4-1234569",
        "showroom_fax": "",
        "email": "info@abctrading.ae"
      },
      "tax_registration_number": "100012345600003",
      "excise_registration_number": ""
    },
    "invoice_details": {
      "invoice_number": "INV-2024-001234",
      "invoice_date": "2024-01-15",
      "invoice_type": "Tax Invoice",
      "order_number": "ORD-5678",
      "order_date": "2024-01-10",
      "page_number": "1/2",
      "purchase_order_number": "PO-2024-100",
      "due_date": "2024-02-14",
      "payment_terms": "Net 30",
      "personnel": {
        "sales_person": "John Doe",
        "supervisor": "Jane Smith",
        "merchandiser": "Bob Johnson"
      }
    },
    "customer_details": {
      "customer_code": "CUST-001",
      "name": "XYZ Corporation",
      "address": "456 Client Avenue, Abu Dhabi",
      "phone": "+971-2-9876543",
      "email": "accounts@xyzcorp.ae",
      "trn": "100098765400001",
      "customer_vat": "5%"
    }
  },
  "document_type": "invoice",
  "company": {
    "name": "ABC Trading LLC",
    "address": {
      "street": "123 Business Street",
      "city": "Dubai",
      "state": "",
      "zip": "12345",
      "country": "UAE"
    },
    "contact": {
      "phone": "+971-4-1234567",
      "email": "info@abctrading.ae",
      "website": "www.abctrading.ae"
    },
    "tax_id": "100012345600003"
  },
  "bill_to": {
    "name": "XYZ Corporation",
    "company": "XYZ Corporation",
    "address": {
      "street": "456 Client Avenue",
      "city": "Abu Dhabi",
      "state": "",
      "zip": "",
      "country": "UAE"
    },
    "phone": "+971-2-9876543",
    "email": "accounts@xyzcorp.ae",
    "customer_id": "CUST-001"
  },
  "ship_to": {
    "name": "XYZ Corporation - Warehouse",
    "company": "XYZ Corporation",
    "address": {
      "street": "789 Warehouse Road",
      "city": "Sharjah",
      "state": "",
      "zip": "",
      "country": "UAE"
    }
  },
  "line_items": [
    {
      "line_number": 1,
      "prod_code": "PROD-001",
      "barcode": "1234567890123",
      "product_name": "Widget A",
      "description": "Premium Widget Type A",
      "packing": "Box of 12",
      "unit": "Box",
      "unit_of_measure": "BOX",
      "qty": 10,
      "quantity": 10,
      "list_value": 1200.00,
      "unit_price": 100.00,
      "gross_amount": 1000.00,
      "discount": 50.00,
      "taxed": true,
      "vat_percent": 5.0,
      "net_value": 950.00,
      "excise": 0,
      "total_incl_excise": 950.00,
      "vat_amount": 47.50,
      "amount": 997.50
    },
    {
      "line_number": 2,
      "prod_code": "PROD-002",
      "barcode": "1234567890124",
      "product_name": "Widget B",
      "description": "Standard Widget Type B",
      "packing": "Box of 24",
      "unit": "Box",
      "unit_of_measure": "BOX",
      "qty": 5,
      "quantity": 5,
      "list_value": 750.00,
      "unit_price": 150.00,
      "gross_amount": 750.00,
      "discount": 25.00,
      "taxed": true,
      "vat_percent": 5.0,
      "net_value": 725.00,
      "excise": 0,
      "total_incl_excise": 725.00,
      "vat_amount": 36.25,
      "amount": 761.25
    }
  ],
  "summary": {
    "subtotal": 1750.00,
    "discount_total": 75.00,
    "taxable_amount": 1675.00,
    "tax_rate_percent": 5.0,
    "vat_total": 83.75,
    "shipping": 0,
    "other_charges": 0,
    "total_amount": 1758.75,
    "amount_paid": 0,
    "balance_due": 1758.75,
    "currency": "AED"
  },
  "payment_instructions": {
    "payable_to": "ABC Trading LLC",
    "payment_method": "Bank Transfer",
    "bank_details": {
      "bank_name": "Emirates NBD",
      "account_name": "ABC Trading LLC",
      "account_number": "1234567890",
      "ifsc_swift": "EBILAEAD"
    },
    "notes": [
      "Payment due within 30 days",
      "Late payment subject to 2% monthly interest"
    ]
  },
  "codes": [
    {
      "type": "QR",
      "value": "https://invoice.abctrading.ae/verify/INV-2024-001234",
      "confidence": 0.98
    }
  ],
  "footer": {
    "totals_summary": {
      "total_discount": 75.00,
      "total_net_inv_value": 1675.00,
      "list_value_total": 1950.00,
      "total_excise": 0,
      "total_incl_excise": 1675.00,
      "total_vat_aed": 83.75,
      "total_incl_vat_aed": 1758.75,
      "amount_in_words": "One Thousand Seven Hundred Fifty Eight AED and 75 Fils"
    },
    "remarks_and_notes": {
      "rebate_note": "Special discount applied",
      "payment_terms": "Net 30 days",
      "return_policy": "Returns accepted within 14 days",
      "delivery_remarks": "Free delivery for orders above AED 1000"
    },
    "processing_info": {
      "prepared_by": "System",
      "printed_by": "Admin",
      "print_timestamp": "2024-01-15 09:30:00",
      "warehouse_loc": "WH-DXB-01"
    },
    "notes": [
      "This is a computer-generated invoice",
      "No signature required"
    ],
    "thank_you_note": "Thank you for your business!"
  },
  "_meta": {
    "ocr_pages": 2,
    "gemini_status": "success",
    "processing_time": 12.5,
    "warnings": [],
    "barcode_detected": true
  }
}
```

**Error Response (400 - Invalid File):**
```json
{
  "detail": "Only PDF files are supported"
}
```

**Error Response (500 - Processing Error):**
```json
{
  "error": "Internal processing error",
  "detail": "Failed to convert PDF: poppler not found",
  "result": {
    "header": {...},
    "...": "...",
    "_meta": {
      "ocr_pages": 0,
      "gemini_status": "error",
      "processing_time": 0.5,
      "warnings": ["Critical error: poppler not found"]
    }
  }
}
```

---

### 4. Batch Extract

Extract data from multiple invoices in one request.

**Endpoint:** `POST /extract-invoice-batch`

**Content-Type:** `multipart/form-data`

**Parameters:**
- `files` (required): Multiple PDF files

**Request:**
```bash
curl -X POST "http://localhost:8000/extract-invoice-batch" \
  -F "files=@invoice1.pdf" \
  -F "files=@invoice2.pdf" \
  -F "files=@invoice3.pdf" \
  -o batch_result.json
```

**Response:**
```json
{
  "results": [
    {
      "filename": "invoice1.pdf",
      "success": true,
      "data": {
        "header": {...},
        "...": "..."
      }
    },
    {
      "filename": "invoice2.pdf",
      "success": true,
      "data": {
        "header": {...},
        "...": "..."
      }
    },
    {
      "filename": "invoice3.pdf",
      "success": false,
      "error": "Failed to convert PDF"
    }
  ]
}
```

---

### 5. Detailed Health Check

Get detailed component health status.

**Endpoint:** `GET /health`

**Request:**
```bash
curl http://localhost:8000/health
```

**Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00",
  "components": {
    "pdf_processor": true,
    "ocr_engine": true,
    "gemini_client": true,
    "invoice_mapper": true
  }
}
```

---

## Response Metadata

Every extraction response includes a `_meta` object:

```json
{
  "_meta": {
    "ocr_pages": 2,
    "gemini_status": "success",
    "processing_time": 12.5,
    "warnings": [],
    "barcode_detected": true
  }
}
```

**Fields:**
- `ocr_pages`: Number of pages processed
- `gemini_status`: `"success"`, `"failed"`, `"error"`, or `"not_attempted"`
- `processing_time`: Total processing time in seconds
- `warnings`: List of non-critical issues encountered
- `barcode_detected`: Whether barcodes were found

---

## Schema Guarantees

✅ **Always returns valid JSON**
✅ **Always matches the universal schema**
✅ **All fields present (never missing)**
✅ **Missing values are `null` or `""`**
✅ **No extra fields (except `_meta`)**
✅ **Structure never changes**

---

## Error Handling

The API implements robust error handling:

1. **Retry Logic**: Gemini failures retry 3 times with exponential backoff
2. **Fallback**: Returns empty schema if extraction fails
3. **Never Crashes**: Always returns valid JSON response
4. **Detailed Errors**: Check `_meta.warnings` for issues

---

## Rate Limits

**Default:** No rate limiting (configure in production)

**Recommended Production Limits:**
- 10 requests/minute per IP
- 100 requests/hour per API key

---

## File Size Limits

**Maximum PDF Size:** 50 MB (configurable)

**Maximum Pages:** No limit (performance degrades beyond 20 pages)

---

## Performance

**Typical Processing Times:**
- 1 page: 5-8 seconds
- 2 pages: 8-12 seconds
- 3 pages: 10-15 seconds
- 5+ pages: 15-30 seconds

**Factors affecting speed:**
- Number of pages
- Image quality
- Document complexity
- Network latency to Gemini API

---

## Examples

### Extract and Parse Specific Fields

```python
import requests

# Extract invoice
url = "http://localhost:8000/extract-invoice"
files = {"file": open("invoice.pdf", "rb")}
response = requests.post(url, files=files)
data = response.json()

# Parse specific fields
invoice_num = data["header"]["invoice_details"]["invoice_number"]
invoice_date = data["header"]["invoice_details"]["invoice_date"]
vendor = data["header"]["vendor_details"]["company_name_en"]
customer = data["header"]["customer_details"]["name"]
total = data["summary"]["total_amount"]
currency = data["summary"]["currency"]

print(f"Invoice: {invoice_num}")
print(f"Date: {invoice_date}")
print(f"From: {vendor}")
print(f"To: {customer}")
print(f"Total: {total} {currency}")

# Get line items
for item in data["line_items"]:
    print(f"  - {item['product_name']}: {item['qty']} x {item['unit_price']} = {item['amount']}")

# Check processing metadata
meta = data["_meta"]
print(f"\nProcessed {meta['ocr_pages']} page(s) in {meta['processing_time']}s")
print(f"Gemini Status: {meta['gemini_status']}")
```

### Error Handling

```python
import requests

try:
    url = "http://localhost:8000/extract-invoice"
    files = {"file": open("invoice.pdf", "rb")}
    response = requests.post(url, files=files, timeout=180)
    
    if response.status_code == 200:
        data = response.json()
        
        # Check for warnings
        if data["_meta"]["warnings"]:
            print("Warnings:", data["_meta"]["warnings"])
        
        # Check Gemini status
        if data["_meta"]["gemini_status"] != "success":
            print("Warning: LLM extraction failed, using fallback")
        
        return data
    else:
        print(f"Error: HTTP {response.status_code}")
        return None

except requests.Timeout:
    print("Request timed out")
except Exception as e:
    print(f"Error: {str(e)}")
```

---

## OpenAPI Documentation

Interactive API documentation available at:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

---

## Postman Collection

Import this collection to test with Postman:

```json
{
  "info": {
    "name": "Invoice Extraction Engine",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    {
      "name": "Extract Invoice",
      "request": {
        "method": "POST",
        "header": [],
        "body": {
          "mode": "formdata",
          "formdata": [
            {
              "key": "file",
              "type": "file",
              "src": ""
            }
          ]
        },
        "url": {
          "raw": "http://localhost:8000/extract-invoice",
          "protocol": "http",
          "host": ["localhost"],
          "port": "8000",
          "path": ["extract-invoice"]
        }
      }
    }
  ]
}
```

---

## Support

For API issues or questions:
1. Check `_meta` field in response
2. Review logs for detailed errors
3. Test with `/health` endpoint
4. Verify file format is PDF
5. Check file size < 50MB
