#!/usr/bin/env python3
"""
API quality benchmark for production-readiness checks.

Runs N notes against /api/analyze and reports:
- success/failure and 5xx rates
- average quality score
- invalid tags based on taxonomy
- notes without tags
- RAG hit rate (via pilier_1_univers_produit.matched_products)

Example:
  python scripts/benchmark_api_quality.py --limit 100 --runs 3
"""

from __future__ import annotations

import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd
import requests


RETRY_STATUSES = {429, 500, 502, 503, 504}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run API quality benchmark")
    parser.add_argument("--dataset", default="LVMH_Realistic_Merged_CA001-100.csv")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--api-base", default="https://lvmh-api-570069708764.europe-west9.run.app")
    parser.add_argument("--email", default="advisor@lvmh.com")
    parser.add_argument("--password", default=os.getenv("DEMO_PASSWORD", "lvmh"))
    parser.add_argument(
        "--taxonomy",
        default="config/taxonomy_v2.2.json",
        help="Path to taxonomy used for tag validation",
    )
    parser.add_argument(
        "--output-json",
        default="benchmark_api_quality_100x3_prod.json",
        help="Summary JSON output path",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for per-run CSV outputs",
    )
    return parser.parse_args()


def _load_valid_tags(taxonomy_path: str) -> set[str]:
    data = json.loads(Path(taxonomy_path).read_text(encoding="utf-8"))
    core_tags = data.get("core_tags", {})
    tags: set[str] = set()
    for values in core_tags.values():
        tags.update(values or [])
    return tags


def _is_valid_tag(tag: str, valid_tags: set[str]) -> bool:
    if tag in valid_tags:
        return True
    if tag.startswith("shopping_with_") or tag.startswith("gift_for_"):
        return True
    return False


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


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    arr = sorted(values)
    idx = int(round((p / 100.0) * (len(arr) - 1)))
    return float(arr[idx])


def _login(api_base: str, email: str, password: str) -> str:
    resp = requests.post(
        f"{api_base}/api/auth/login",
        data={"username": email, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def _post_with_retries(
    api_base: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    max_retries: int = 4,
) -> requests.Response:
    last_resp: requests.Response | None = None
    for attempt in range(max_retries + 1):
        resp = requests.post(
            f"{api_base}/api/analyze",
            json=payload,
            headers=headers,
            timeout=240,
        )
        last_resp = resp
        if resp.status_code not in RETRY_STATUSES:
            return resp
        if attempt < max_retries:
            time.sleep(min(8.0, 1.2 * (2**attempt)))
    return last_resp  # type: ignore[return-value]


def _run_once(
    run_index: int,
    notes: List[Dict[str, Any]],
    api_base: str,
    email: str,
    password: str,
    valid_tags: set[str],
) -> Tuple[Dict[str, Any], pd.DataFrame]:
    token = _login(api_base, email, password)
    headers = {"Authorization": f"Bearer {token}"}

    rows: List[Dict[str, Any]] = []

    for note in notes:
        note_id = str(note["ID"])
        text = str(note["Transcription"] or "")
        lang = (str(note.get("Language") or "") or "AUTO").upper()
        payload = {"text": text, "language": lang}

        status_code: int | None = None
        error_detail = ""
        started = time.time()

        try:
            resp = _post_with_retries(api_base, payload, headers=headers, max_retries=4)
            if resp.status_code == 401:
                token = _login(api_base, email, password)
                headers = {"Authorization": f"Bearer {token}"}
                resp = _post_with_retries(api_base, payload, headers=headers, max_retries=1)

            status_code = resp.status_code
            latency_ms = (time.time() - started) * 1000.0

            if status_code != 200:
                error_detail = (resp.text or "")[:400]
                rows.append(
                    {
                        "run": run_index,
                        "id": note_id,
                        "status_code": status_code,
                        "ok": 0,
                        "quality_score": 0.0,
                        "tags_count": 0,
                        "invalid_tags_count": 0,
                        "invalid_tags": "",
                        "rag_hit": 0,
                        "rgpd_sensitive": 0,
                        "tier": None,
                        "processing_time_ms": latency_ms,
                        "error": error_detail,
                        "text_preview": text[:180],
                    }
                )
                continue

            data = resp.json()
            tags = list(data.get("tags") or [])
            invalid_tags = [tag for tag in tags if not _is_valid_tag(tag, valid_tags)]
            quality = _safe_quality((data.get("meta_analysis") or {}).get("quality_score"))

            p1 = data.get("pilier_1_univers_produit") or {}
            matched = p1.get("matched_products") or []
            rag_hit = 1 if isinstance(matched, list) and len(matched) > 0 else 0

            routing = data.get("routing") or {}
            rgpd = data.get("rgpd") or {}

            processing_time_ms = float(data.get("processing_time_ms") or latency_ms)

            rows.append(
                {
                    "run": run_index,
                    "id": note_id,
                    "status_code": status_code,
                    "ok": 1,
                    "quality_score": quality,
                    "tags_count": len(tags),
                    "invalid_tags_count": len(invalid_tags),
                    "invalid_tags": "|".join(invalid_tags),
                    "rag_hit": rag_hit,
                    "rgpd_sensitive": 1 if bool(rgpd.get("contains_sensitive")) else 0,
                    "tier": routing.get("tier"),
                    "processing_time_ms": processing_time_ms,
                    "error": "",
                    "text_preview": text[:180],
                }
            )
        except Exception as exc:
            latency_ms = (time.time() - started) * 1000.0
            rows.append(
                {
                    "run": run_index,
                    "id": note_id,
                    "status_code": None,
                    "ok": 0,
                    "quality_score": 0.0,
                    "tags_count": 0,
                    "invalid_tags_count": 0,
                    "invalid_tags": "",
                    "rag_hit": 0,
                    "rgpd_sensitive": 0,
                    "tier": None,
                    "processing_time_ms": latency_ms,
                    "error": str(exc)[:400],
                    "text_preview": text[:180],
                }
            )

    df = pd.DataFrame(rows)
    total = len(df)
    ok_df = df[df["ok"] == 1]

    status_counts = {
        str(k): int(v) for k, v in df["status_code"].fillna("exception").value_counts().to_dict().items()
    }
    http_5xx = int(df["status_code"].apply(lambda x: isinstance(x, (int, float)) and 500 <= int(x) <= 599).sum())

    worst = ok_df.sort_values(by=["quality_score", "tags_count"], ascending=[True, True]).head(10)
    worst_notes = [
        {
            "id": str(r["id"]),
            "quality_score": round(float(r["quality_score"]), 2),
            "tags_count": int(r["tags_count"]),
            "invalid_tags_count": int(r["invalid_tags_count"]),
            "rag_hit": bool(r["rag_hit"]),
            "tier": None if pd.isna(r["tier"]) else int(r["tier"]),
            "text_preview": str(r["text_preview"]),
        }
        for _, r in worst.iterrows()
    ]

    processing_values = [float(x) for x in ok_df["processing_time_ms"].tolist()]
    run_result = {
        "run": run_index,
        "input_notes": total,
        "successful_notes": int(ok_df.shape[0]),
        "failed_notes": int(total - ok_df.shape[0]),
        "success_rate_pct": round((ok_df.shape[0] / total * 100.0) if total else 0.0, 2),
        "http_5xx_count": http_5xx,
        "status_counts": status_counts,
        "avg_quality_score": round(float(ok_df["quality_score"].mean()) if not ok_df.empty else 0.0, 2),
        "notes_without_tags": int((ok_df["tags_count"] == 0).sum()) if not ok_df.empty else 0,
        "invalid_tags_total": int(ok_df["invalid_tags_count"].sum()) if not ok_df.empty else 0,
        "notes_with_invalid_tags": int((ok_df["invalid_tags_count"] > 0).sum()) if not ok_df.empty else 0,
        "rag_hit_rate_pct": round(float(ok_df["rag_hit"].mean() * 100.0) if not ok_df.empty else 0.0, 2),
        "avg_processing_time_ms": round(float(ok_df["processing_time_ms"].mean()) if not ok_df.empty else 0.0, 2),
        "p95_processing_time_ms": round(_percentile(processing_values, 95), 2),
        "worst_10_notes": worst_notes,
    }
    return run_result, df


def _evaluate_thresholds(run_result: Dict[str, Any]) -> Dict[str, bool]:
    return {
        "success_rate>=99": float(run_result["success_rate_pct"]) >= 99.0,
        "http_5xx==0": int(run_result["http_5xx_count"]) == 0,
        "invalid_tags_total==0": int(run_result["invalid_tags_total"]) == 0,
        "avg_quality_score>=80": float(run_result["avg_quality_score"]) >= 80.0,
        "rag_hit_rate>=85": float(run_result["rag_hit_rate_pct"]) >= 85.0,
        "notes_without_tags==0": int(run_result["notes_without_tags"]) == 0,
    }


def main() -> int:
    args = parse_args()
    dataset_path = Path(args.dataset)
    out_json = Path(args.output_json)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(dataset_path)
    required = ["ID", "Transcription", "Language"]
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in dataset: {missing}")

    notes = df[required].fillna("").to_dict("records")[: args.limit]
    valid_tags = _load_valid_tags(args.taxonomy)

    run_results: List[Dict[str, Any]] = []
    for i in range(1, args.runs + 1):
        result, run_df = _run_once(
            run_index=i,
            notes=notes,
            api_base=args.api_base,
            email=args.email,
            password=args.password,
            valid_tags=valid_tags,
        )
        thresholds = _evaluate_thresholds(result)
        result["thresholds"] = thresholds
        result["all_thresholds_pass"] = all(thresholds.values())
        run_csv = out_dir / f"benchmark_api_quality_run{i}.csv"
        run_df.to_csv(run_csv, index=False, encoding="utf-8")
        result["output_csv"] = str(run_csv).replace("\\", "/")
        run_results.append(result)

    overall = {
        "dataset": str(dataset_path),
        "input_notes_per_run": args.limit,
        "runs": args.runs,
        "api_base": args.api_base,
        "results": run_results,
        "all_runs_pass": all(r.get("all_thresholds_pass", False) for r in run_results),
    }

    out_json.parent.mkdir(parents=True, exist_ok=True)
    out_json.write_text(json.dumps(overall, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(overall, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
