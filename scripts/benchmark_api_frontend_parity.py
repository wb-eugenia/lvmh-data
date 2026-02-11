#!/usr/bin/env python3
"""
Benchmark parity between direct pipeline output and API output consumed by frontend.

Usage:
  python scripts/benchmark_api_frontend_parity.py
  python scripts/benchmark_api_frontend_parity.py --limit 20 --output-json benchmark_api_frontend_parity_20_latest.json
"""

import argparse
import asyncio
import json
import math
import os
import sys
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd
import requests

# Add project root to import path
sys.path.append(os.getcwd())

from src.pipeline_async import AsyncPipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run API vs pipeline parity benchmark")
    parser.add_argument(
        "--dataset",
        default="LVMH_Realistic_Merged_CA001-100.csv",
        help="CSV dataset with columns ID, Transcription, Language",
    )
    parser.add_argument("--limit", type=int, default=20, help="Number of notes to benchmark")
    parser.add_argument("--api-base", default="http://127.0.0.1:8080", help="API base URL")
    parser.add_argument("--email", default="advisor@lvmh.com", help="Advisor email")
    parser.add_argument("--password", default=os.getenv("DEMO_PASSWORD", "lvmh"), help="Advisor password")
    parser.add_argument(
        "--output-json",
        default="benchmark_api_frontend_parity_20_latest.json",
        help="Path for benchmark output",
    )
    return parser.parse_args()


def _jaccard(a: List[str], b: List[str]) -> float:
    sa = set(a or [])
    sb = set(b or [])
    if not sa and not sb:
        return 1.0
    union = sa | sb
    if not union:
        return 1.0
    return len(sa & sb) / len(union)


def _required_frontend_fields() -> List[str]:
    return [
        "id",
        "tags",
        "routing",
        "rgpd",
        "meta_analysis",
        "pilier_1_univers_produit",
        "pilier_2_profil_client",
        "pilier_3_hospitalite_care",
        "pilier_4_action_business",
        "processing_time_ms",
    ]


def _missing_fields(payload: Dict[str, Any]) -> List[str]:
    required = _required_frontend_fields()
    return [field for field in required if field not in payload]


async def _run_pipeline(notes: List[Dict[str, str]]) -> Dict[str, Any]:
    pipeline = AsyncPipeline(use_cache=False, use_semantic_cache=False, use_cross_validation=True)
    results = await pipeline.process_batch(notes)
    by_id = {
        str(r.id): {
            "tier": r.routing.tier,
            "rgpd_sensitive": bool(r.rgpd.contains_sensitive),
            "tags": list(r.extraction.tags if r.extraction else []),
        }
        for r in results
    }
    return by_id


def _login(api_base: str, email: str, password: str) -> str:
    resp = requests.post(
        f"{api_base}/api/auth/login",
        data={"username": email, "password": password},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]


def main() -> int:
    args = parse_args()
    df = pd.read_csv(args.dataset)
    required = ["ID", "Transcription", "Language"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in dataset: {missing}")

    rows = df[required].fillna("").to_dict("records")[: args.limit]
    notes = [{"ID": str(r["ID"]), "Transcription": r["Transcription"], "Language": r["Language"]} for r in rows]

    pipeline_by_id = asyncio.run(_run_pipeline(notes))
    token = _login(args.api_base, args.email, args.password)
    headers = {"Authorization": f"Bearer {token}"}

    api_success = 0
    api_errors: List[Dict[str, Any]] = []
    tier_matches = 0
    rgpd_matches = 0
    jaccards: List[float] = []
    missing_required_fields = 0
    invalid_quality_range = 0

    for note in notes:
        pid = str(note["ID"])
        payload = {"text": note["Transcription"], "language": note["Language"] or "AUTO"}

        try:
            resp = requests.post(f"{args.api_base}/api/analyze", json=payload, headers=headers, timeout=120)
            if resp.status_code != 200:
                api_errors.append({"id": pid, "status": resp.status_code, "detail": resp.text[:200]})
                continue
            api_data = resp.json()
            api_success += 1
        except Exception as exc:  # pragma: no cover - network/runtime variability
            api_errors.append({"id": pid, "status": "exception", "detail": str(exc)})
            continue

        missing_fields = _missing_fields(api_data)
        if missing_fields:
            missing_required_fields += 1

        quality = float((api_data.get("meta_analysis") or {}).get("quality_score") or 0.0)
        quality_pct = quality * 100.0 if quality <= 1.0 else quality
        if quality_pct < 0.0 or quality_pct > 100.0 or math.isnan(quality_pct):
            invalid_quality_range += 1

        direct = pipeline_by_id.get(pid)
        if not direct:
            continue

        if (api_data.get("routing") or {}).get("tier") == direct["tier"]:
            tier_matches += 1
        if bool((api_data.get("rgpd") or {}).get("contains_sensitive")) == direct["rgpd_sensitive"]:
            rgpd_matches += 1

        jaccards.append(_jaccard(api_data.get("tags") or [], direct["tags"]))

    compared = max(1, api_success)
    result = {
        "input_notes": len(notes),
        "api_success": api_success,
        "api_errors": api_errors,
        "tier_match_rate_pct": round((tier_matches / compared) * 100.0, 2),
        "rgpd_match_rate_pct": round((rgpd_matches / compared) * 100.0, 2),
        "avg_tag_jaccard": round(sum(jaccards) / len(jaccards), 4) if jaccards else 0.0,
        "min_tag_jaccard": round(min(jaccards), 4) if jaccards else 0.0,
        "max_tag_jaccard": round(max(jaccards), 4) if jaccards else 0.0,
        "missing_required_fields": missing_required_fields,
        "invalid_quality_range": invalid_quality_range,
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
