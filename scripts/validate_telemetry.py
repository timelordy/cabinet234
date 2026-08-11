#!/usr/bin/env python3
"""Validate the public, non-secret telemetry discovery document."""

from __future__ import annotations

import json
import sys
import urllib.parse
from pathlib import Path

ALLOWED_PRODUCT_IDS = {"unitools-eom", "unitools-lintels"}


def validate(path: Path) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    if set(data) != {"schemaVersion", "enabled", "ingestUrl", "productIds"} or data["schemaVersion"] != "1.0":
        raise ValueError("unsupported telemetry discovery contract")
    if not isinstance(data["enabled"], bool):
        raise ValueError("enabled must be boolean")
    product_ids = data["productIds"]
    if (
        not isinstance(product_ids, list)
        or any(not isinstance(item, str) for item in product_ids)
        or len(product_ids) != len(set(product_ids))
        or set(product_ids) - ALLOWED_PRODUCT_IDS
    ):
        raise ValueError("productIds must be a unique public product allowlist")
    if data["enabled"] is False:
        if data["ingestUrl"] is not None or product_ids:
            raise ValueError("disabled telemetry must not publish an endpoint or products")
        return
    if not product_ids:
        raise ValueError("enabled telemetry must admit at least one product")
    url = str(data["ingestUrl"] or "")
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "https" or not parsed.hostname or not parsed.hostname.endswith(".apigw.yandexcloud.net"):
        raise ValueError("enabled telemetry must use a Yandex API Gateway HTTPS endpoint")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("telemetry endpoint contains forbidden URL parts")


if __name__ == "__main__":
    try:
        validate(Path(sys.argv[1] if len(sys.argv) > 1 else "telemetry.json"))
        print("telemetry discovery document is valid")
    except Exception as error:
        print("telemetry validation failed: %s" % error, file=sys.stderr)
        raise SystemExit(1)
