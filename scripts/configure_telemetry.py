#!/usr/bin/env python3
"""Enable or disable the public Yandex telemetry endpoint projection."""

from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path

ALLOWED_PRODUCT_IDS = ("unitools-eom", "unitools-lintels")


def validate_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".apigw.yandexcloud.net"):
        raise ValueError("telemetry URL must be an HTTPS Yandex API Gateway endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("telemetry URL must not contain credentials, a query, or a fragment")
    return url.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--disable", action="store_true")
    parser.add_argument("--product-id", action="append", choices=ALLOWED_PRODUCT_IDS, dest="product_ids")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "telemetry.json")
    args = parser.parse_args()
    if args.disable == bool(args.url):
        parser.error("provide exactly one of --url or --disable")
    if args.url and not args.product_ids:
        parser.error("enabled telemetry requires at least one --product-id")
    data = {
        "schemaVersion": "1.0",
        "enabled": not args.disable,
        "ingestUrl": validate_url(args.url) if args.url else None,
        "productIds": list(dict.fromkeys(args.product_ids or [])),
    }
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
