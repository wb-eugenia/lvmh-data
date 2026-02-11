.PHONY: install run test clean pipeline docker benchmark-quality benchmark-parity check-slo backup-db db-upgrade db-downgrade db-stamp go-live-check

# ===== SETUP =====
install:
	pip install -r requirements.txt

# ===== DEVELOPMENT =====
run:
	streamlit run app.py

test:
	python -m pytest tests/ -v

lint:
	flake8 src/ scripts/ --max-line-length=120

# ===== PIPELINE =====
clean-text:
	python src/text_cleaner.py

pipeline:
	python scripts/run_wave2_pipeline.py

pipeline-nocache:
	python scripts/run_wave2_pipeline.py --no-cache

benchmark-quality:
	python scripts/benchmark_quality_pipeline.py --dataset LVMH_Realistic_Merged_CA001-100.csv --limit 100

benchmark-parity:
	python scripts/benchmark_api_frontend_parity.py --limit 20 --output-json benchmark_api_frontend_parity_20_latest.json

check-slo:
	python scripts/check_slo.py --benchmark benchmark_quality_100_pipeline_prod_ready.json

backup-db:
	python scripts/backup_db.py --output-dir backups

db-upgrade:
	alembic upgrade head

db-downgrade:
	alembic downgrade -1

db-stamp:
	alembic stamp head

go-live-check:
	python scripts/go_live_checklist.py --benchmark benchmark_quality_100_pipeline_prod_ready.json

compare:
	python scripts/compare_waves.py

validate-rgpd:
	python scripts/validate_rgpd.py

# ===== CLEANUP =====
clean:
	rm -rf cache/wave2/*.json
	rm -rf logs/*.log
	rm -rf __pycache__ .pytest_cache
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true

clean-all: clean
	rm -rf outputs/*.xlsx outputs/*.csv outputs/*.json outputs/*.parquet

# ===== DOCKER =====
docker-build:
	docker build -t lvmh-voice-tag .

docker-run:
	docker run -p 8501:8501 --env-file .env -v $(PWD)/outputs:/app/outputs lvmh-voice-tag

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

# ===== HELP =====
help:
	@echo "LVMH Voice to Tag - Available commands:"
	@echo ""
	@echo "  make install       Install dependencies"
	@echo "  make run           Start Streamlit app"
	@echo "  make test          Run tests"
	@echo ""
	@echo "  make pipeline      Run full Wave 2 pipeline"
	@echo "  make compare       Compare Wave 1 vs Wave 2"
	@echo "  make validate-rgpd Interactive RGPD validation"
	@echo ""
	@echo "  make docker-build  Build Docker image"
	@echo "  make docker-run    Run Docker container"
