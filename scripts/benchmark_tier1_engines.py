"""
Benchmark Tier1 extraction engines (regex vs aho).

Usage:
  python scripts/benchmark_tier1_engines.py --input LVMH_Realistic_Merged_CA001-100.csv --sizes 100 500
"""

from __future__ import annotations

import argparse
import statistics
import time
from pathlib import Path
from typing import List

import pandas as pd

from config.production import settings
from src.tier1_rules import Tier1RulesEngine


def _load_notes(path: Path) -> List[str]:
    if path.suffix.lower() == ".csv":
        df = pd.read_csv(path)
    elif path.suffix.lower() in {".xlsx", ".xls"}:
        df = pd.read_excel(path)
    else:
        raise ValueError("Unsupported file format. Use CSV/XLSX.")

    column = "Transcription" if "Transcription" in df.columns else ("text" if "text" in df.columns else None)
    if column is None:
        raise ValueError("Input file must contain 'Transcription' or 'text' column.")
    return [str(v).strip() for v in df[column].dropna().tolist() if str(v).strip()]


def _run_once(notes: List[str], engine_name: str) -> dict:
    settings.tier1_match_engine = engine_name
    engine = Tier1RulesEngine()

    # warm-up
    for note in notes[:5]:
        engine.extract(note)

    timings = []
    for note in notes:
        start = time.perf_counter()
        engine.extract(note)
        timings.append((time.perf_counter() - start) * 1000.0)

    sorted_timings = sorted(timings)
    p95_idx = max(0, int(len(sorted_timings) * 0.95) - 1)
    return {
        "engine_requested": engine_name,
        "engine_used": engine.match_engine,
        "samples": len(notes),
        "mean_ms": round(statistics.mean(timings), 4),
        "p95_ms": round(sorted_timings[p95_idx], 4),
        "max_ms": round(max(timings), 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark Tier1 regex vs aho extraction.")
    parser.add_argument("--input", required=True, help="CSV/XLSX input file.")
    parser.add_argument("--sizes", nargs="+", type=int, default=[100, 500], help="Sample sizes to benchmark.")
    args = parser.parse_args()

    source = Path(args.input)
    if not source.exists():
        raise FileNotFoundError(f"Input file not found: {source}")

    notes = _load_notes(source)
    if not notes:
        raise ValueError("No notes found in input.")

    print(f"source={source}")
    print(f"notes_available={len(notes)}")

    for size in args.sizes:
        sample = notes[: min(size, len(notes))]
        print(f"\nsize={len(sample)}")
        for engine_name in ("regex", "aho"):
            result = _run_once(sample, engine_name)
            print(
                f"engine={result['engine_requested']} used={result['engine_used']} "
                f"mean_ms={result['mean_ms']} p95_ms={result['p95_ms']} max_ms={result['max_ms']}"
            )


if __name__ == "__main__":
    main()

