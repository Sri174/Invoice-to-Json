FROM python:3.11-slim

# Prevent python from writing pyc files
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies required for OCR and PDF processing
RUN apt-get update && apt-get install -y \
    poppler-utils \
    tesseract-ocr \
    libgl1 \
    libglib2.0-0 \
    libsm6 \
    libxext6 \
    libxrender-dev \
    libgomp1 \
    libzbar0 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Ensure poppler binaries are accessible
ENV PATH="/usr/bin:${PATH}"

# Set working directory
WORKDIR /app

# Copy dependency file
COPY requirements.txt .

# Install python dependencies
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt

# Copy project code
COPY . .

# Create output directory
RUN mkdir -p runs

# Expose port used by Render
EXPOSE 10000

# Start FastAPI server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "10000", "--workers", "2"]
