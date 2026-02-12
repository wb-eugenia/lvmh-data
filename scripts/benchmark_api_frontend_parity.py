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
import re
import sys
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Any

import pandas as pd
import requests

# Add project root to import path
sys.path.append(os.getcwd())

TRUTHY_VALUES = {"1", "true", "yes", "y", "oui"}


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
    parser.add_argument(
        "--source",
        choices=["legacy", "parity_probe"],
        default="legacy",
        help="Parity source: legacy compares /api/analyze to local direct pipeline; parity_probe compares in-prod probe projections.",
    )
    parser.add_argument(
        "--pipeline-profile",
        default="single_note",
        help="Pipeline profile used for direct run (single_note or batch_csv)",
    )
    parser.add_argument(
        "--weights-tier",
        type=float,
        default=0.4,
        help="Combined parity weight for tier parity",
    )
    parser.add_argument(
        "--weights-rgpd",
        type=float,
        default=0.4,
        help="Combined parity weight for RGPD parity",
    )
    parser.add_argument(
        "--weights-tags",
        type=float,
        default=0.2,
        help="Combined parity weight for tags parity (Jaccard)",
    )
    parser.add_argument(
        "--low-tag-jaccard-threshold",
        type=float,
        default=0.5,
        help="Threshold under which a note is flagged as low_tag_jaccard",
    )
    parser.add_argument(
        "--direct-disable-rgpd-llm",
        action="store_true",
        help="Disable RGPD LLM only for direct pipeline side to reduce nondeterministic parity noise.",
    )
    parser.add_argument(
        "--direct-sequential",
        action="store_true",
        help="Run direct pipeline note-by-note (process_note) to mirror /api/analyze behavior.",
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


def _normalize_tags(tags: Any) -> List[str]:
    if isinstance(tags, str):
        source = tags.split(",")
    elif isinstance(tags, (list, tuple, set)):
        source = list(tags)
    else:
        return []
    normalized: List[str] = []
    seen = set()
    for raw in source:
        if raw is None:
            continue
        value = str(raw).strip()
        if not value:
            continue
        # Canonical token to prevent false mismatches from accents/casing/separators.
        ascii_value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
        key = re.sub(r"[^a-z0-9]+", "_", ascii_value.lower()).strip("_")
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)
        normalized.append(key)
    return normalized


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    normalized = str(value or "").strip().lower()
    if not normalized:
        return False
    return normalized in TRUTHY_VALUES


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


async def _run_pipeline(
    notes: List[Dict[str, str]],
    profile: str,
    disable_rgpd_llm: bool = False,
    sequential: bool = False,
) -> Dict[str, Any]:
    if disable_rgpd_llm:
        os.environ["ENABLE_RGPD_LLM"] = "0"
    from src.pipeline_async import AsyncPipeline

    pipeline = AsyncPipeline(use_cache=False, use_semantic_cache=False, use_cross_validation=True)
    if sequential:
        results = []
        for note in notes:
            output = await pipeline.process_note(
                note,
                profile=profile,
                save_to_cache=False,
            )
            if output is not None:
                results.append(output)
    else:
        results = await pipeline.process_batch(notes, profile=profile)
    by_id = {
        str(r.id): {
            "tier": r.routing.tier,
            "rgpd_sensitive": _to_bool(r.rgpd.contains_sensitive),
            "tags": _normalize_tags(r.extraction.tags if r.extraction else []),
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


def _post_json_with_retries(
    api_base: str,
    path: str,
    payload: Dict[str, Any],
    headers: Dict[str, str],
    max_retries: int = 4,
) -> requests.Response:
    retry_statuses = {429, 500, 502, 503, 504}
    last_resp: requests.Response | None = None
    for attempt in range(max_retries + 1):
        resp = requests.post(
            f"{api_base}{path}",
            json=payload,
            headers=headers,
            timeout=180,
        )
        last_resp = resp
        if resp.status_code not in retry_statuses:
            return resp
        if attempt < max_retries:
            sleep_s = min(8.0, 1.5 * (2 ** attempt))
            time.sleep(sleep_s)
    return last_resp


def main() -> int:
    args = parse_args()
    weight_sum = args.weights_tier + args.weights_rgpd + args.weights_tags
    if weight_sum <= 0:
        raise ValueError("weights sum must be > 0")

    # Normalize weights so callers can pass either percentages or raw values.
    weight_tier = args.weights_tier / weight_sum
    weight_rgpd = args.weights_rgpd / weight_sum
    weight_tags = args.weights_tags / weight_sum

    df = pd.read_csv(args.dataset)
    required = ["ID", "Transcription", "Language"]
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"Missing columns in dataset: {missing}")

    rows = df[required].fillna("").to_dict("records")[: args.limit]
    notes = [{"ID": str(r["ID"]), "Transcription": r["Transcription"], "Language": r["Language"]} for r in rows]

    if args.source == "parity_probe" and args.email == "advisor@lvmh.com":
        args.email = "manager@lvmh.com"

    pipeline_by_id: Dict[str, Any] = {}
    if args.source == "legacy":
        pipeline_by_id = asyncio.run(
            _run_pipeline(
                notes,
                profile=args.pipeline_profile,
                disable_rgpd_llm=args.direct_disable_rgpd_llm,
                sequential=args.direct_sequential,
            )
        )

    token = _login(args.api_base, args.email, args.password)
    headers = {"Authorization": f"Bearer {token}"}

    api_success = 0
    api_errors: List[Dict[str, Any]] = []
    tier_matches = 0
    rgpd_matches = 0
    jaccards: List[float] = []
    note_mismatches: List[Dict[str, Any]] = []
    missing_required_fields = 0
    invalid_quality_range = 0

    for note in notes:
        pid = str(note["ID"])
        if args.source == "parity_probe":
            endpoint_path = "/api/analyze/parity-probe"
            payload = {
                "text": note["Transcription"],
                "language": note["Language"] or "AUTO",
                "profile": args.pipeline_profile,
            }
        else:
            endpoint_path = "/api/analyze"
            payload = {"text": note["Transcription"], "language": note["Language"] or "AUTO"}

        try:
            resp = _post_json_with_retries(
                args.api_base,
                endpoint_path,
                payload,
                headers=headers,
                max_retries=4,
            )

            # Token may expire during long benchmarks. Refresh once then retry.
            if resp.status_code == 401:
                token = _login(args.api_base, args.email, args.password)
                headers = {"Authorization": f"Bearer {token}"}
                resp = _post_json_with_retries(
                    args.api_base,
                    endpoint_path,
                    payload,
                    headers=headers,
                    max_retries=1,
                )

            if resp.status_code != 200:
                api_errors.append({"id": pid, "status": resp.status_code, "detail": resp.text[:200]})
                continue

            api_data = resp.json()
            api_success += 1
        except Exception as exc:  # pragma: no cover - network/runtime variability
            api_errors.append({"id": pid, "status": "exception", "detail": str(exc)})
            continue

        if args.source == "parity_probe":
            missing_fields = [
                field
                for field in ["api_projection", "runtime_projection", "diff", "meta"]
                if field not in api_data
            ]
            if missing_fields:
                missing_required_fields += 1

            api_projection = api_data.get("api_projection") or {}
            runtime_projection = api_data.get("runtime_projection") or {}
            api_tier = api_projection.get("tier")
            api_sensitive = _to_bool(api_projection.get("rgpd_contains_sensitive"))
            api_tags = _normalize_tags(api_projection.get("tags"))
            direct = {
                "tier": runtime_projection.get("tier"),
                "rgpd_sensitive": _to_bool(runtime_projection.get("rgpd_contains_sensitive")),
                "tags": _normalize_tags(runtime_projection.get("tags")),
            }
            if direct["tier"] is None:
                note_mismatches.append(
                    {
                        "id": pid,
                        "tier_mismatch": None,
                        "rgpd_mismatch": None,
                        "low_tag_jaccard": None,
                        "tag_jaccard": None,
                        "api_tier": api_tier,
                        "pipeline_tier": None,
                        "api_contains_sensitive": api_sensitive,
                        "pipeline_contains_sensitive": None,
                        "api_tag_count": len(api_tags),
                        "pipeline_tag_count": None,
                        "missing_required_fields": missing_fields,
                        "error": "runtime_projection_missing",
                    }
                )
                continue
        else:
            missing_fields = _missing_fields(api_data)
            if missing_fields:
                missing_required_fields += 1

            quality = float((api_data.get("meta_analysis") or {}).get("quality_score") or 0.0)
            quality_pct = quality * 100.0 if quality <= 1.0 else quality
            if quality_pct < 0.0 or quality_pct > 100.0 or math.isnan(quality_pct):
                invalid_quality_range += 1

            direct = pipeline_by_id.get(pid)
            if not direct:
                note_mismatches.append(
                    {
                        "id": pid,
                        "tier_mismatch": None,
                        "rgpd_mismatch": None,
                        "low_tag_jaccard": None,
                        "tag_jaccard": None,
                        "api_tier": (api_data.get("routing") or {}).get("tier"),
                        "pipeline_tier": None,
                        "api_contains_sensitive": _to_bool((api_data.get("rgpd") or {}).get("contains_sensitive")),
                        "pipeline_contains_sensitive": None,
                        "api_tag_count": len(_normalize_tags(api_data.get("tags"))),
                        "pipeline_tag_count": None,
                        "missing_required_fields": missing_fields,
                        "error": "pipeline_result_missing",
                    }
                )
                continue

            api_tier = (api_data.get("routing") or {}).get("tier")
            api_sensitive = _to_bool((api_data.get("rgpd") or {}).get("contains_sensitive"))
            api_tags = _normalize_tags(api_data.get("tags"))

        tier_match = api_tier == direct["tier"]
        if tier_match:
            tier_matches += 1

        rgpd_match = api_sensitive == direct["rgpd_sensitive"]
        if rgpd_match:
            rgpd_matches += 1

        tag_jaccard = _jaccard(api_tags, direct["tags"])
        jaccards.append(tag_jaccard)

        note_mismatches.append(
            {
                "id": pid,
                "tier_mismatch": not tier_match,
                "rgpd_mismatch": not rgpd_match,
                "low_tag_jaccard": tag_jaccard < args.low_tag_jaccard_threshold,
                "tag_jaccard": round(tag_jaccard, 4),
                "api_tier": api_tier,
                "pipeline_tier": direct["tier"],
                "api_contains_sensitive": api_sensitive,
                "pipeline_contains_sensitive": direct["rgpd_sensitive"],
                "api_tag_count": len(api_tags),
                "pipeline_tag_count": len(direct["tags"]),
                "missing_required_fields": missing_fields,
            }
        )

    compared_count = len([n for n in note_mismatches if n.get("tag_jaccard") is not None])
    compared = max(1, compared_count)
    tier_match_rate_pct = round((tier_matches / compared) * 100.0, 2)
    rgpd_match_rate_pct = round((rgpd_matches / compared) * 100.0, 2)
    avg_tag_jaccard = (sum(jaccards) / len(jaccards)) if jaccards else 0.0
    avg_tag_jaccard_pct = round(avg_tag_jaccard * 100.0, 2)
    combined_score = (
        (tier_match_rate_pct * weight_tier)
        + (rgpd_match_rate_pct * weight_rgpd)
        + (avg_tag_jaccard_pct * weight_tags)
    )

    tier_mismatch_count = sum(1 for n in note_mismatches if n.get("tier_mismatch") is True)
    rgpd_mismatch_count = sum(1 for n in note_mismatches if n.get("rgpd_mismatch") is True)
    low_tag_jaccard_count = sum(1 for n in note_mismatches if n.get("low_tag_jaccard") is True)

    result = {
        "dataset": args.dataset,
        "source": args.source,
        "pipeline_profile": args.pipeline_profile,
        "input_notes": len(notes),
        "api_success": api_success,
        "api_errors": api_errors,
        "api_success_rate_pct": round((api_success / max(1, len(notes))) * 100.0, 2),
        "compared_notes": compared_count,
        "weights": {
            "tier": round(weight_tier, 4),
            "rgpd": round(weight_rgpd, 4),
            "tags": round(weight_tags, 4),
        },
        "tier_match_rate_pct": tier_match_rate_pct,
        "rgpd_match_rate_pct": rgpd_match_rate_pct,
        "avg_tag_jaccard": round(avg_tag_jaccard, 4),
        "avg_tag_jaccard_pct": avg_tag_jaccard_pct,
        "min_tag_jaccard": round(min(jaccards), 4) if jaccards else 0.0,
        "max_tag_jaccard": round(max(jaccards), 4) if jaccards else 0.0,
        "combined_parity_score_pct": round(combined_score, 2),
        "missing_required_fields": missing_required_fields,
        "invalid_quality_range": invalid_quality_range,
        "mismatch_counts": {
            "tier_mismatch": tier_mismatch_count,
            "rgpd_mismatch": rgpd_mismatch_count,
            "low_tag_jaccard": low_tag_jaccard_count,
        },
        "per_note_diff": note_mismatches,
    }

    output_path = Path(args.output_json)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
