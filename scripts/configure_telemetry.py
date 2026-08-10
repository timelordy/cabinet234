#!/usr/bin/env python3
"""Enable or disable the public Yandex telemetry endpoint projection."""

from __future__ import annotations

import argparse
import json
import urllib.parse
from pathlib import Path


def validate_url(url: str) -> str:
    parsed = urllib.parse.urlparse(url.strip())
    allowed = (".apigw.yandexcloud.net", ".functions.yandexcloud.net")
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(allowed):
        raise ValueError("telemetry URL must be an HTTPS Yandex Cloud endpoint")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError("telemetry URL must not contain credentials or a fragment")
    return url.strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--url")
    parser.add_argument("--disable", action="store_true")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parents[1] / "telemetry.json")
    args = parser.parse_args()
    if args.disable == bool(args.url):
        parser.error("provide exactly one of --url or --disable")
    data = {
        "schemaVersion": "1.0",
        "enabled": not args.disable,
        "ingestUrl": validate_url(args.url) if args.url else None,
    }
    args.output.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
