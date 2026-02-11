#!/usr/bin/env python3
"""
Compare 3 execution modes on the same dataset:
1) Direct pipeline batch
2) API sequential
3) API parallel (N workers)

Outputs a JSON summary with throughput, latency and quality indicators.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import statistics
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import requests

# local import
import sys
sys.path.append(os.getcwd())
from src.pipeline_async import AsyncPipeline  # noqa: E402


RETRY_STATUSES = {429, 500, 502, 503, 504}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare direct pipeline vs API modes")
    parser.add_argument("--dataset", default="LVMH_Realistic_Merged_CA001-100.csv")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--api-base", default="https://lvmh-api-570069708764.europe-west9.run.app")
    parser.add_argument("--email", default="advisor@lvmh.com")
    parser.add_argument("--password", default=os.getenv("DEMO_PASSWORD", "lvmh"))
    parser.add_argument("--parallel-workers", type=int, default=5)
    parser.add_argument("--login-timeout", type=int, default=90)
    parser.add_argument("--analyze-timeout", type=int, default=300)
    parser.add_argument("--max-retries", type=int, default=4)
    parser.add_argument("--output-json", default="output/compare_pipeline_api_modes_100.json")
    return parser.parse_args()


def _safe_quality(value: Any) -> float:
    try:
        score = float(value or 0.0)
    except Exception:
        return 0.0
    if math.isnan(score) or math.isinf(score):
        return 0.0
    if score <= 1.0:
        score *= 100.0
    return max(0.0, min(100.0, score))


def _mean(values: List[float]) -> float:
    return float(statistics.mean(values)) if values else 0.0


def _p95(values: List[float]) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    idx = int(round(0.95 * (len(arr) - 1)))
    return float(arr[idx])


def _summarize_common(
    mode: str,
    input_notes: int,
    successful_notes: int,
    failed_notes: int,
    wall_s: float,
    qualities: List[float],
    tags_count: List[int],
    rag_hits: List[int],
    note_times_ms: List[float],
    status_counts: Dict[str, int] | None = None,
) -> Dict[str, Any]:
    return {
        "mode": mode,
        "input_notes": input_notes,
        "successful_notes": successful_notes,
        "failed_notes": failed_notes,
        "success_rate_pct": round((successful_notes / input_notes * 100.0) if input_notes else 0.0, 2),
        "wall_duration_s": round(wall_s, 2),
        "throughput_notes_per_min": round((successful_notes / wall_s * 60.0) if wall_s > 0 else 0.0, 2),
        "avg_quality_score": round(_mean(qualities), 2),
        "avg_tags_per_note": round(_mean([float(x) for x in tags_count]), 2),
        "rag_hit_rate_pct": round(_mean([float(x) for x in rag_hits]) * 100.0, 2),
        "avg_note_processing_time_ms": round(_mean(note_times_ms), 2),
        "p95_note_processing_time_ms": round(_p95(note_times_ms), 2),
        "status_counts": status_counts or {},
    }


async def run_direct_pipeline(notes: List[Dict[str, Any]]) -> Dict[str, Any]:
    started = time.time()
    pipeline = AsyncPipeline(use_cache=False, use_semantic_cache=False, use_cross_validation=True)
    results = await pipeline.process_batch(notes)
    wall_s = time.time() - started

    qualities: List[float] = []
    tags_count: List[int] = []
    rag_hits: List[int] = []
    note_times_ms: List[float] = []

    for result in results:
        ext = result.extraction
        qualities.append(_safe_quality(ext.meta_analysis.quality_score if ext else 0.0))
        tags = list(ext.tags if ext else [])
        tags_count.append(len(tags))
        matched = ext.pilier_1_univers_produit.matched_products if ext else []
        rag_hits.append(1 if matched else 0)
        note_times_ms.append(float(result.processing_time_ms or 0.0))

    return _summarize_common(
        mode="pipeline_direct_batch",
        input_notes=len(notes),
        successful_notes=len(results),
        failed_notes=len(notes) - len(results),
        wall_s=wall_s,
        qualities=qualities,
        tags_count=tags_count,
        rag_hits=rag_hits,
        note_times_ms=note_times_ms,
    )


def _login(api_base: str, email: str, password: str, timeout_s: int, max_retries: int) -> str:
    last_exc: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            r = requests.post(
                f"{api_base}/api/auth/login",
                data={"username": email, "password": password},
                timeout=timeout_s,
            )
            r.raise_for_status()
            return r.json()["access_token"]
        except Exception as exc:  # pragma: no cover
            last_exc = exc
            if attempt < max_retries:
                time.sleep(min(8.0, 1.2 * (2**attempt)))
    raise RuntimeError(f"Login failed after retries: {last_exc}")


def _post_with_retries(
    api_base: str,
    token: str,
    payload: Dict[str, Any],
    max_retries: int,
    analyze_timeout_s: int,
) -> requests.Response:
    headers = {"Authorization": f"Bearer {token}"}
    last_resp: requests.Response | None = None
    for attempt in range(max_retries + 1):
        resp = requests.post(
            f"{api_base}/api/analyze",
            json=payload,
            headers=headers,
            timeout=analyze_timeout_s,
        )
        last_resp = resp
        if resp.status_code not in RETRY_STATUSES:
            return resp
        if attempt < max_retries:
            time.sleep(min(6.0, 1.2 * (2**attempt)))
    return last_resp  # type: ignore[return-value]


def run_api_mode(
    notes: List[Dict[str, Any]],
    api_base: str,
    email: str,
    password: str,
    workers: int,
    login_timeout: int,
    analyze_timeout: int,
    max_retries: int,
) -> Dict[str, Any]:
    started = time.time()
    try:
        token = _login(api_base, email, password, timeout_s=login_timeout, max_retries=max_retries)
    except Exception:
        wall_s = time.time() - started
        mode = "api_sequential" if workers <= 1 else f"api_parallel_{workers}w"
        return _summarize_common(
            mode=mode,
            input_notes=len(notes),
            successful_notes=0,
            failed_notes=len(notes),
            wall_s=wall_s,
            qualities=[],
            tags_count=[],
            rag_hits=[],
            note_times_ms=[],
            status_counts={"login_failed": len(notes)},
        )

    qualities: List[float] = []
    tags_count: List[int] = []
    rag_hits: List[int] = []
    note_times_ms: List[float] = []
    status_counts: Dict[str, int] = {}

    def _one(note: Dict[str, Any]) -> Dict[str, Any]:
        note_started = time.time()
        payload = {
            "text": str(note.get("Transcription") or ""),
            "language": str(note.get("Language") or "AUTO"),
        }
        try:
            resp = _post_with_retries(
                api_base,
                token,
                payload,
                max_retries=max_retries,
                analyze_timeout_s=analyze_timeout,
            )
            if resp.status_code == 401:
                # Token may expire during long runs. Refresh and retry once.
                refreshed = _login(
                    api_base,
                    email,
                    password,
                    timeout_s=login_timeout,
                    max_retries=max_retries,
                )
                resp = _post_with_retries(
                    api_base,
                    refreshed,
                    payload,
                    max_retries=1,
                    analyze_timeout_s=analyze_timeout,
                )
            code = str(resp.status_code)
            if resp.status_code == 200:
                data = resp.json()
                q = _safe_quality((data.get("meta_analysis") or {}).get("quality_score"))
                tags = list(data.get("tags") or [])
                p1 = data.get("pilier_1_univers_produit") or {}
                matched = p1.get("matched_products") or []
                pt = float(data.get("processing_time_ms") or ((time.time() - note_started) * 1000.0))
                return {"ok": 1, "status": code, "quality": q, "tags": len(tags), "rag": 1 if matched else 0, "pt": pt}
            return {"ok": 0, "status": code, "quality": 0.0, "tags": 0, "rag": 0, "pt": (time.time() - note_started) * 1000.0}
        except Exception:
            return {
                "ok": 0,
                "status": "exception",
                "quality": 0.0,
                "tags": 0,
                "rag": 0,
                "pt": (time.time() - note_started) * 1000.0,
            }

    if workers <= 1:
        results = [_one(n) for n in notes]
    else:
        results = []
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futures = [ex.submit(_one, n) for n in notes]
            for f in as_completed(futures):
                results.append(f.result())

    success = 0
    for r in results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1
        if r["ok"] == 1:
            success += 1
            qualities.append(float(r["quality"]))
            tags_count.append(int(r["tags"]))
            rag_hits.append(int(r["rag"]))
            note_times_ms.append(float(r["pt"]))

    wall_s = time.time() - started
    failed = len(notes) - success
    mode = "api_sequential" if workers <= 1 else f"api_parallel_{workers}w"
    return _summarize_common(
        mode=mode,
        input_notes=len(notes),
        successful_notes=success,
        failed_notes=failed,
        wall_s=wall_s,
        qualities=qualities,
        tags_count=tags_count,
        rag_hits=rag_hits,
        note_times_ms=note_times_ms,
        status_counts=status_counts,
    )


def main() -> int:
    args = parse_args()
    df = pd.read_csv(args.dataset)
    required = ["ID", "Transcription", "Language"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    notes = df[required].fillna("").to_dict("records")[: args.limit]
    direct = asyncio.run(run_direct_pipeline(notes))
    api_seq = run_api_mode(
        notes,
        args.api_base,
        args.email,
        args.password,
        workers=1,
        login_timeout=args.login_timeout,
        analyze_timeout=args.analyze_timeout,
        max_retries=args.max_retries,
    )
    api_par = run_api_mode(
        notes,
        args.api_base,
        args.email,
        args.password,
        workers=args.parallel_workers,
        login_timeout=args.login_timeout,
        analyze_timeout=args.analyze_timeout,
        max_retries=args.max_retries,
    )

    summary = {
        "dataset": args.dataset,
        "limit": args.limit,
        "api_base": args.api_base,
        "modes": [direct, api_seq, api_par],
    }

    Path(args.output_json).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output_json).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
