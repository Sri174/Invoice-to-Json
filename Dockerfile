FROM python:3.11-slim

# System dependencies for OCR, image processing, and barcode reading
RUN apt-get update && apt-get install -y \
    tesseract-ocr \
    libzbar0 \
    libgl1 \
    libgomp1 \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create runs directory for output files
RUN mkdir -p runs

EXPOSE 8000

# Run production FastAPI server with uvicorn
# Use main.py for new production system or api_server.py for legacy
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2
