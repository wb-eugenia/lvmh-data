# Wave 2 Pipeline Documentation

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    WAVE 2 PIPELINE                          │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   RAW CSV       │    │  TEXT CLEANER   │    │   RGPD FILTER   │
│   (300 notes)   │───▶│  Remove fillers │───▶│  LLM detection  │
│   CA_101-400    │    │  5 languages    │    │  Anonymize      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                                      │
                                                      ▼
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│  EXPORT         │    │   VALIDATION    │    │  TAG EXTRACTOR  │
│  Excel/CSV/     │◀───│  Confidence     │◀───│  GPT-4o-mini    │
│  Parquet/JSON   │    │  Cache          │    │  Taxonomy v2    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
```

## Components

### 1. Text Cleaner (`src/text_cleaner.py`)
- **Purpose**: Remove verbal fillers (euh, um, etc.) to reduce tokens and improve extraction quality
- **Languages**: FR, EN, IT, ES, DE
- **Performance**: ~27% average compression, ~1ms/note
- **Output**: Cleaned transcription + stats

### 2. Cache Manager (`src/cache_manager.py`)
- **Purpose**: Avoid re-processing expensive operations
- **Strategy**: MD5 hash of text + step name
- **Benefit**: Re-runs are instant, cost-free

### 3. RGPD Filter (`src/rgpd_filter.py`)
- **Purpose**: Detect and anonymize GDPR Article 9 sensitive data
- **Categories**: Mental health, physical health, family conflicts, religion, politics, etc.
- **Method**: LLM-based contextual detection (not keyword matching)
- **Compliance**: Anonymizes before storage

### 4. Cost Tracker (`src/cost_tracker.py`)
- **Purpose**: Real-time API cost monitoring
- **Tracks**: Input/output tokens per step
- **Reports**: Total cost breakdown

### 5. Tag Extractor (`src/extractor.py`)
- **Purpose**: Extract structured tags from transcriptions
- **Model**: GPT-4o-mini
- **Taxonomy**: 98 tags across 8 categories
- **Output**: Tags, confidence, metadata

## Performance Benchmarks

| Step | Time/Note | API Cost/Note |
|------|-----------|---------------|
| Cleaning | ~1ms | $0 |
| RGPD Filter | ~3s | ~$0.003 |
| Tag Extraction | ~5s | ~$0.005 |
| **Total** | ~8s | ~$0.008 |

**Full Pipeline (300 notes)**:
- First run: ~40 minutes, ~$2.40
- Cached run: ~30 seconds, $0

## Usage

```bash
# Full pipeline
python scripts/run_wave2_pipeline.py

# Without cache (force reprocess)
python scripts/run_wave2_pipeline.py --no-cache

# Custom input/output
python scripts/run_wave2_pipeline.py -i data/custom.csv -o outputs/custom
```

## Output Files

| File | Format | Purpose |
|------|--------|---------|
| `wave2_final_dataset.xlsx` | Excel | Human review |
| `wave2_final_dataset.csv` | CSV | Portability |
| `wave2_final_dataset.parquet` | Parquet | Performance |
| `wave2_final_dataset.json` | JSON | API integration |
| `wave2_rgpd_report.json` | JSON | Compliance audit |
| `wave2_stats.json` | JSON | Pipeline metrics |

## RGPD Compliance

### What is detected:
- Mental health conditions (burnout, depression, anxiety)
- Physical health (diseases, disabilities) - NOT allergies
- Family conflicts (contentious divorce, custody disputes)
- Religious beliefs
- Political opinions
- Sexual orientation

### What is NOT flagged:
- Food allergies (business-relevant)
- Material allergies (nickel, latex)
- Dietary preferences (vegan, vegetarian)
- Simple "divorced" status without conflict context
- Profession

### Anonymization
Sensitive spans are replaced with: `[RGPD_CATEGORY_REDACTED]`
