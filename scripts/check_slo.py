#!/usr/bin/env python3
"""
Validate benchmark outputs against SLO thresholds.

Usage:
  python scripts/check_slo.py --benchmark benchmark_quality_100_pipeline_prod_ready.json
"""

import argparse
import json
import sys
from pathlib import Path


def parse_args():
    parser = argparse.ArgumentParser(description="Check pipeline SLO thresholds")
    parser.add_argument("--benchmark", required=True, help="Benchmark JSON path")
    parser.add_argument("--min-quality", type=float, default=75.0, help="Minimum avg quality score")
    parser.add_argument("--min-rag-hit-rate", type=float, default=80.0, help="Minimum RAG hit rate percent")
    parser.add_argument("--max-p95-ms", type=float, default=5000.0, help="Maximum p95 processing time (ms)")
    parser.add_argument("--max-failed-notes", type=int, default=0, help="Maximum failed notes")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    benchmark_path = Path(args.benchmark)
    data = json.loads(benchmark_path.read_text(encoding="utf-8"))

    failures = []
    quality = float(data.get("quality_metrics", {}).get("avg_quality_score", 0.0))
    rag_hit_rate = float(data.get("rag_metrics", {}).get("hit_rate_pct", 0.0))
    p95 = float(data.get("quality_metrics", {}).get("p95_processing_time_ms", 0.0))
    failed_notes = int(data.get("failed_notes", 0))

    if quality < args.min_quality:
        failures.append(f"avg_quality_score={quality} < {args.min_quality}")
    if rag_hit_rate < args.min_rag_hit_rate:
        failures.append(f"rag_hit_rate={rag_hit_rate}% < {args.min_rag_hit_rate}%")
    if p95 > args.max_p95_ms:
        failures.append(f"p95_processing_time_ms={p95} > {args.max_p95_ms}")
    if failed_notes > args.max_failed_notes:
        failures.append(f"failed_notes={failed_notes} > {args.max_failed_notes}")

    if failures:
        print("SLO CHECK FAILED")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("SLO CHECK PASSED")
    print(f"- avg_quality_score={quality}")
    print(f"- rag_hit_rate_pct={rag_hit_rate}")
    print(f"- p95_processing_time_ms={p95}")
    print(f"- failed_notes={failed_notes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
