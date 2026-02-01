# Build Stage for React
FROM node:18-alpine as frontend-build
WORKDIR /app/frontend
COPY frontend-v2/package*.json ./
RUN npm ci
COPY frontend-v2/ ./
RUN npm run build

# Python Runtime Stage
FROM python:3.9-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN pip install groq sqlalchemy passlib python-jose bcrypt

# Copy Backend Code
COPY src/ ./src/

# Copy React Build from previous stage
COPY --from=frontend-build /app/frontend/dist ./frontend-v2/dist

# Expose port
EXPOSE 8080

# Environment variables
ENV PORT=8080
ENV HOST=0.0.0.0

# Run Command
CMD ["uvicorn", "src.event_pipeline:app", "--host", "0.0.0.0", "--port", "8080"]
