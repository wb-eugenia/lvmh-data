#!/usr/bin/env python3
"""
Go-live checklist validator for LVMH Voice-to-Tag.

This script validates technical prerequisites before production rollout.
It is intentionally conservative: non-critical checks are reported but do not fail the run.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import requests


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run go-live checklist")
    parser.add_argument("--api-base", default="http://127.0.0.1:8080", help="Backend base URL")
    parser.add_argument(
        "--benchmark",
        default="benchmark_quality_100_pipeline_prod_ready.json",
        help="Benchmark JSON used for SLO check",
    )
    parser.add_argument(
        "--output-json",
        default="go_live_checklist_report.json",
        help="Output report path",
    )
    parser.add_argument(
        "--strict-env",
        action="store_true",
        help="Fail if required deployment env vars are missing in local environment",
    )
    return parser.parse_args()


def check_file(path: str) -> Dict[str, Any]:
    exists = Path(path).exists()
    return {
        "name": f"file:{path}",
        "ok": exists,
        "critical": True,
        "detail": "present" if exists else "missing",
    }


def check_api_endpoint(base: str, endpoint: str, timeout: int = 8) -> Dict[str, Any]:
    url = f"{base.rstrip('/')}{endpoint}"
    try:
        response = requests.get(url, timeout=timeout)
        ok = response.status_code == 200
        return {
            "name": f"api:{endpoint}",
            "ok": ok,
            "critical": endpoint in {"/health", "/ready"},
            "detail": f"status={response.status_code}",
        }
    except Exception as exc:
        return {
            "name": f"api:{endpoint}",
            "ok": False,
            "critical": endpoint in {"/health", "/ready"},
            "detail": str(exc),
        }


def check_benchmark_slo(path: str) -> Dict[str, Any]:
    p = Path(path)
    if not p.exists():
        return {
            "name": "slo:benchmark_file",
            "ok": False,
            "critical": True,
            "detail": f"missing file: {path}",
        }

    data = json.loads(p.read_text(encoding="utf-8"))
    quality = float(data.get("quality_metrics", {}).get("avg_quality_score", 0.0))
    rag = float(data.get("rag_metrics", {}).get("hit_rate_pct", 0.0))
    p95 = float(data.get("quality_metrics", {}).get("p95_processing_time_ms", 0.0))
    failed = int(data.get("failed_notes", 0))

    checks = {
        "quality>=75": quality >= 75.0,
        "rag_hit_rate>=85": rag >= 85.0,
        "p95<=5000ms": p95 <= 5000.0,
        "failed_notes==0": failed == 0,
    }
    ok = all(checks.values())
    return {
        "name": "slo:benchmark_thresholds",
        "ok": ok,
        "critical": True,
        "detail": {
            "quality": quality,
            "rag_hit_rate_pct": rag,
            "p95_processing_time_ms": p95,
            "failed_notes": failed,
            "checks": checks,
        },
    }


def check_env(strict: bool) -> List[Dict[str, Any]]:
    required = [
        "OPENAI_API_KEY",
        "MISTRAL_API_KEY",
        "JWT_SECRET_KEY",
        "DATABASE_URL",
    ]
    checks: List[Dict[str, Any]] = []
    for key in required:
        value = os.getenv(key, "").strip()
        checks.append(
            {
                "name": f"env:{key}",
                "ok": bool(value),
                "critical": strict,
                "detail": "set" if value else "missing",
            }
        )

    db_url = os.getenv("DATABASE_URL", "")
    app_env = os.getenv("ENV", os.getenv("APP_ENV", "development")).lower()
    if app_env in {"production", "prod"}:
        checks.append(
            {
                "name": "env:database_is_postgres_in_prod",
                "ok": db_url.startswith("postgresql"),
                "critical": strict,
                "detail": db_url if db_url else "missing DATABASE_URL",
            }
        )
    return checks


def build_report(args: argparse.Namespace) -> Dict[str, Any]:
    checks: List[Dict[str, Any]] = []

    # Files and migrations
    checks.append(check_file("alembic.ini"))
    checks.append(check_file("alembic/env.py"))
    checks.append(check_file("alembic/versions/20260211_0001_initial_schema.py"))
    checks.append(check_file("scripts/benchmark_quality_pipeline.py"))
    checks.append(check_file("scripts/check_slo.py"))
    checks.append(check_file("scripts/load_test_k6.js"))
    checks.append(check_file(".github/workflows/ci.yml"))
    checks.append(check_file(".github/workflows/deploy-api-cloud-run.yml"))
    checks.append(check_file(".github/workflows/deploy-frontend-cloudflare.yml"))
    checks.append(check_file(".github/workflows/db-backup.yml"))

    # API checks
    checks.append(check_api_endpoint(args.api_base, "/health"))
    checks.append(check_api_endpoint(args.api_base, "/ready"))
    checks.append(check_api_endpoint(args.api_base, "/metrics/prometheus"))

    # SLO checks
    checks.append(check_benchmark_slo(args.benchmark))

    # Env checks
    checks.extend(check_env(strict=args.strict_env))

    critical_failures = [c for c in checks if c["critical"] and not c["ok"]]
    overall_ok = len(critical_failures) == 0

    return {
        "overall_ok": overall_ok,
        "critical_failures": critical_failures,
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    report = build_report(args)

    output_path = Path(args.output_json)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    return 0 if report["overall_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
