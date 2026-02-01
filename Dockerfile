# LVMH Cloud Run Dockerfile
# Optimized for Production (API Mode)

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Prevent Python from writing pyc files and buffering stdout
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

# Install system dependencies (lightweight)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
# We copy src, api, and config explicitly to keep image clean, or just copy . if .dockerignore is good
COPY . .

# Create non-root user for security (Cloud Run best practice)
RUN addgroup --system appgroup && adduser --system --group appuser
USER appuser

# Cloud Run injects PORT environment variable (default 8080)
ENV PORT=8080

# Run FastAPI with Uvicorn
# Uses the PORT environment variable
CMD sh -c "uvicorn api.main:app --host 0.0.0.0 --port ${PORT} --workers 2"
