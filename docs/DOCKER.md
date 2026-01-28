# LVMH Voice to Tag - Docker & Makefile

## Dockerfile

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Expose Streamlit port
EXPOSE 8501

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8501/_stcore/health || exit 1

# Default command
CMD ["streamlit", "run", "app.py", "--server.address", "0.0.0.0"]

## docker-compose.yml

version: '3.8'

services:
  web:
    build: .
    ports:
      - "8501:8501"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
    volumes:
      - ./outputs:/app/outputs
      - ./cache:/app/cache
      - ./logs:/app/logs
    restart: unless-stopped

## Makefile commands

```makefile
# Common commands
.PHONY: install run clean test pipeline docker

install:
	pip install -r requirements.txt

run:
	streamlit run app.py

test:
	pytest tests/ -v

clean:
	rm -rf cache/wave2/*.json
	rm -rf logs/*.log
	rm -rf __pycache__ .pytest_cache

# Pipeline commands
pipeline-clean:
	python src/text_cleaner.py

pipeline-full:
	python scripts/run_wave2_pipeline.py

pipeline-nocache:
	python scripts/run_wave2_pipeline.py --no-cache

compare:
	python scripts/compare_waves.py

validate-rgpd:
	python scripts/validate_rgpd.py

# Docker commands
docker-build:
	docker build -t lvmh-voice-tag .

docker-run:
	docker run -p 8501:8501 --env-file .env lvmh-voice-tag

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down
```
