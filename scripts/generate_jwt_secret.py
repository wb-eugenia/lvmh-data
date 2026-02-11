#!/usr/bin/env python3
"""
Generate or validate JWT secrets for LVMH Voice-to-Tag.

Usage:
  python scripts/generate_jwt_secret.py
  python scripts/generate_jwt_secret.py --length 64
  python scripts/generate_jwt_secret.py --write-env .env
"""

from __future__ import annotations

import argparse
import os
import secrets
import string
from pathlib import Path


ALPHABET = string.ascii_letters + string.digits + "-_"
MIN_LENGTH = 32


def generate_secret(length: int) -> str:
    return "".join(secrets.choice(ALPHABET) for _ in range(length))


def upsert_env_key(env_path: Path, key: str, value: str) -> None:
    lines = []
    if env_path.exists():
        lines = env_path.read_text(encoding="utf-8").splitlines()

    updated = False
    output = []
    for line in lines:
        if line.startswith(f"{key}="):
            output.append(f"{key}={value}")
            updated = True
        else:
            output.append(line)

    if not updated:
        output.append(f"{key}={value}")

    env_path.write_text("\n".join(output) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate a JWT secret (min 32 chars).")
    parser.add_argument("--length", type=int, default=48, help="Secret length (>= 32). Default: 48.")
    parser.add_argument("--write-env", type=Path, default=None, help="Optional .env file to update.")
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Do not print secret value to stdout.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force generation even if JWT_SECRET_KEY already exists in environment with valid length.",
    )
    args = parser.parse_args()

    if args.length < MIN_LENGTH:
        raise SystemExit(f"--length must be >= {MIN_LENGTH}")

    existing = os.getenv("JWT_SECRET_KEY", "")
    if existing and len(existing) >= MIN_LENGTH and not args.force:
        if not args.quiet:
            print(f"JWT_SECRET_KEY already set with valid length ({len(existing)} chars).")
        if args.write_env:
            upsert_env_key(args.write_env, "JWT_SECRET_KEY", existing)
            if not args.quiet:
                print(f"Updated {args.write_env} with current JWT_SECRET_KEY.")
        return 0

    secret = generate_secret(args.length)
    if not args.quiet:
        print(secret)
        print(f"Length: {len(secret)}")

    if args.write_env:
        upsert_env_key(args.write_env, "JWT_SECRET_KEY", secret)
        if not args.quiet:
            print(f"Updated {args.write_env} with generated JWT_SECRET_KEY.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
