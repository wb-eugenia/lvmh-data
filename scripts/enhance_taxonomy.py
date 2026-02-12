"""
Generate a taxonomy review queue from historical notes.

This script never writes into config/taxonomy_v*.json directly.
Outputs are produced under outputs/ for human review.
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List

import pandas as pd

from src.lexicon_builder import LexiconBuilder, load_taxonomy


def _load_notes(input_path: Path, text_column: str) -> List[str]:
    if input_path.suffix.lower() == ".csv":
        df = pd.read_csv(input_path)
    elif input_path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(input_path)
    else:
        raise ValueError("Unsupported input format. Use CSV or Excel.")

    if text_column not in df.columns:
        fallback = next((col for col in ["Transcription", "text", "note"] if col in df.columns), None)
        if fallback is None:
            raise ValueError(f"Column '{text_column}' not found and no fallback transcription column available.")
        text_column = fallback

    return [str(v).strip() for v in df[text_column].dropna().tolist() if str(v).strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description="Build taxonomy review queue from historical notes.")
    parser.add_argument("--input", required=True, help="Path to CSV/XLSX notes file.")
    parser.add_argument("--text-column", default="Transcription", help="Transcription column name.")
    parser.add_argument("--taxonomy", default="config/taxonomy_v2.2.json", help="Taxonomy path.")
    parser.add_argument("--output-dir", default="outputs", help="Directory for generated review files.")
    parser.add_argument("--limit", type=int, default=300, help="Max candidates in review queue.")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    taxonomy = load_taxonomy(args.taxonomy)
    notes = _load_notes(input_path, args.text_column)

    builder = LexiconBuilder(language="fr")
    report = builder.build_review_queue(notes, taxonomy, limit=max(10, int(args.limit)))

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"taxonomy_review_queue_{ts}.json"
    csv_path = out_dir / f"taxonomy_review_queue_{ts}.csv"

    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    rows = report.get("review_queue", [])
    pd.DataFrame(rows).to_csv(csv_path, index=False, encoding="utf-8")

    print(f"notes_analyzed={report.get('notes_analyzed', 0)}")
    print(f"candidate_count={report.get('candidate_count', 0)}")
    print(f"json_output={json_path}")
    print(f"csv_output={csv_path}")
    print("policy=review_queue_only_no_auto_merge")


if __name__ == "__main__":
    main()
