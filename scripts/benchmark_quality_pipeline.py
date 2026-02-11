#!/usr/bin/env python3
"""
Reproducible quality benchmark for the async pipeline.

Usage:
  python scripts/benchmark_quality_pipeline.py
  python scripts/benchmark_quality_pipeline.py --dataset LVMH_Realistic_Merged_CA001-100.csv --limit 100
"""

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

# Add project root to import path
sys.path.append(os.getcwd())

from src.pipeline_async import AsyncPipeline
from src.taxonomy import TaxonomyManager


def parse_args():
    parser = argparse.ArgumentParser(description="Run quality benchmark for pipeline_async")
    parser.add_argument(
        "--dataset",
        default="LVMH_Realistic_Merged_CA001-100.csv",
        help="CSV dataset with columns ID, Transcription, Language",
    )
    parser.add_argument("--limit", type=int, default=100, help="Number of notes to benchmark")
    parser.add_argument(
        "--output-json",
        default="benchmark_quality_100_pipeline_prod_ready.json",
        help="Path for benchmark json output",
    )
    parser.add_argument(
        "--output-csv",
        default="output/benchmark_quality_100_notes_metrics.csv",
        help="Path for per-note metrics csv output",
    )
    parser.add_argument("--use-cache", action="store_true", help="Enable cache for benchmark")
    parser.add_argument("--use-semantic-cache", action="store_true", help="Enable semantic cache for benchmark")
    return parser.parse_args()


def _safe_quality_score(value: float) -> float:
    score = float(value or 0.0)
    if score <= 1.0:
        score *= 100.0
    return score


def _percentile(series: pd.Series, p: float) -> float:
    if series.empty:
        return 0.0
    return float(np.percentile(series, p))


async def run(args):
    df = pd.read_csv(args.dataset)
    required = ["ID", "Transcription", "Language"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in dataset: {missing}")

    notes = df[required].fillna("").to_dict("records")[: args.limit]
    pipeline = AsyncPipeline(
        use_cache=args.use_cache,
        use_semantic_cache=args.use_semantic_cache,
        use_cross_validation=True,
    )
    results = await pipeline.process_batch(notes)
    summary = pipeline.get_summary()

    taxonomy = TaxonomyManager("2.2")
    rows = []
    invalid_tags_total = 0
    total_tags = 0
    notes_with_invalid_tags = 0

    for result in results:
        extraction = result.extraction
        tags = extraction.tags if extraction else []
        total_tags += len(tags)

        invalid_count = 0
        for tag in tags:
            if tag.startswith("action:"):
                continue
            if not taxonomy.validate_tag(tag):
                invalid_count += 1
        invalid_tags_total += invalid_count
        if invalid_count > 0:
            notes_with_invalid_tags += 1

        original_len = len((result.original_text or "").strip())
        processed_len = len((result.processed_text or "").strip())
        reduction_pct = ((original_len - processed_len) / original_len * 100.0) if original_len else 0.0

        rows.append(
            {
                "id": result.id,
                "tier": result.routing.tier,
                "quality_score": _safe_quality_score(extraction.meta_analysis.quality_score if extraction else 0),
                "confidence": float(extraction.confidence) if extraction else 0.0,
                "tag_count": len(tags),
                "has_tags": len(tags) > 0,
                "processing_time_ms": float(result.processing_time_ms),
                "rgpd_sensitive": bool(result.rgpd.contains_sensitive),
                "matched_products": len(extraction.pilier_1_univers_produit.matched_products) if extraction else 0,
                "char_reduction_pct": max(0.0, reduction_pct),
                "invalid_tags_count": invalid_count,
            }
        )

    metrics_df = pd.DataFrame(rows)
    Path(args.output_csv).parent.mkdir(parents=True, exist_ok=True)
    metrics_df.to_csv(args.output_csv, index=False, encoding="utf-8")

    p50 = _percentile(metrics_df["processing_time_ms"], 50)
    p95 = _percentile(metrics_df["processing_time_ms"], 95)
    p99 = _percentile(metrics_df["processing_time_ms"], 99)
    filtered_df = metrics_df[metrics_df["processing_time_ms"] <= p99]

    benchmark = {
        "dataset": args.dataset,
        "input_notes": len(notes),
        "successful_notes": len(results),
        "failed_notes": len(notes) - len(results),
        "pipeline_summary": summary,
        "quality_metrics": {
            "avg_quality_score": round(float(metrics_df["quality_score"].mean()), 2),
            "avg_extraction_confidence": round(float(metrics_df["confidence"].mean()), 4),
            "avg_tags_per_note": round(float(metrics_df["tag_count"].mean()), 2),
            "notes_without_tags": int((metrics_df["has_tags"] == False).sum()),
            "invalid_tags_total": int(invalid_tags_total),
            "invalid_tags_rate_pct": round((invalid_tags_total / total_tags * 100.0), 2) if total_tags else 0.0,
            "notes_with_invalid_tags": int(notes_with_invalid_tags),
            "avg_processing_time_ms": round(float(metrics_df["processing_time_ms"].mean()), 3),
            "p50_processing_time_ms": round(p50, 2),
            "p95_processing_time_ms": round(p95, 2),
            "p99_processing_time_ms": round(p99, 2),
            "max_processing_time_ms": round(float(metrics_df["processing_time_ms"].max()), 2),
            "avg_processing_time_ms_excl_top_1pct": round(float(filtered_df["processing_time_ms"].mean()), 3)
            if not filtered_df.empty
            else 0.0,
            "avg_char_reduction_pct": round(float(metrics_df["char_reduction_pct"].mean()), 4),
        },
        "rgpd_metrics": {
            "notes_with_sensitive_data": int(metrics_df["rgpd_sensitive"].sum()),
            "sensitive_rate_pct": round(float(metrics_df["rgpd_sensitive"].mean() * 100.0), 2),
        },
        "rag_metrics": {
            "attempted": int(summary.get("rag", {}).get("attempted", 0)),
            "hits": int(summary.get("rag", {}).get("hits", 0)),
            "hit_rate_pct": round(float(summary.get("rag", {}).get("hit_rate", 0.0)), 2),
            "notes_with_matched_products": int((metrics_df["matched_products"] > 0).sum()),
        },
        "output_metrics_csv": args.output_csv,
    }

    Path(args.output_json).write_text(
        json.dumps(benchmark, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(json.dumps(benchmark, ensure_ascii=False, indent=2))


def main():
    args = parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
