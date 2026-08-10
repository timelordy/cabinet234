#!/usr/bin/env python3
"""Validate the public Cabinet 234 catalog and downloadable artifacts."""

from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Any


CHANNELS = {"stable", "beta", "alpha", "archived"}
VISIBILITY = {"public", "hidden"}
ACTIONS = {"download", "external", "unavailable"}
DOWNLOAD_PREFIX = "https://github.com/timelordy/cabinet234/releases/download/"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("%s must be a non-empty string" % field)
    return value


def _validate_action(product: dict[str, Any]) -> None:
    action = product.get("action")
    if not isinstance(action, dict) or action.get("kind") not in ACTIONS:
        raise ValueError("%s has an invalid action" % product.get("id"))
    _require_text(action.get("label"), "action.label")
    url = action.get("url")
    if action["kind"] == "unavailable" and url is not None:
        raise ValueError("unavailable action must not contain a URL")
    if action["kind"] != "unavailable":
        _require_text(url, "action.url")


def _validate_download(product: dict[str, Any]) -> None:
    action = product["action"]
    artifact = product.get("artifact")
    if action["kind"] != "download":
        if artifact is not None:
            raise ValueError("artifact metadata is allowed only for downloads")
        return
    if not action["url"].startswith(DOWNLOAD_PREFIX):
        raise ValueError("download URL must point to a Cabinet 234 release")
    if not isinstance(artifact, dict):
        raise ValueError("download action requires artifact metadata")
    if artifact.get("format") != "zip" or int(artifact.get("sizeBytes", 0)) <= 0:
        raise ValueError("download artifact size or format is invalid")
    if not SHA256_RE.fullmatch(str(artifact.get("sha256", ""))):
        raise ValueError("download artifact SHA-256 is invalid")


def validate_catalog(data: dict[str, Any]) -> list[dict[str, Any]]:
    if data.get("schemaVersion") != "3.0" or data.get("mode") != "live":
        raise ValueError("unsupported catalog contract")
    _require_text(data.get("generatedAt"), "generatedAt")
    products = data.get("products")
    if not isinstance(products, list):
        raise ValueError("products must be an array")
    ids: set[str] = set()
    for product in products:
        if not isinstance(product, dict):
            raise ValueError("product must be an object")
        product_id = _require_text(product.get("id"), "product.id")
        if product_id in ids:
            raise ValueError("duplicate product id: %s" % product_id)
        ids.add(product_id)
        _require_text(product.get("name"), "product.name")
        _require_text(product.get("summary"), "product.summary")
        if product.get("channel") not in CHANNELS or product.get("visibility") not in VISIBILITY:
            raise ValueError("%s has invalid channel or visibility" % product_id)
        if product.get("visibility") == "hidden" and (product.get("action") or {}).get("url"):
            raise ValueError("hidden products must not expose URLs")
        _validate_action(product)
        _validate_download(product)
    return products


def check_downloads(products: list[dict[str, Any]]) -> None:
    for product in products:
        if product["action"]["kind"] != "download":
            continue
        request = urllib.request.Request(
            product["action"]["url"],
            method="HEAD",
            headers={"User-Agent": "Cabinet234CatalogVerifier/1"},
        )
        with urllib.request.urlopen(request, timeout=30) as response:
            if response.status >= 400:
                raise ValueError("download is unavailable: %s" % product["id"])
            length = response.headers.get("Content-Length")
            expected = int(product["artifact"]["sizeBytes"])
            if length is not None and int(length) != expected:
                raise ValueError("download size differs for %s" % product["id"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("catalog", type=Path)
    parser.add_argument("--check-downloads", action="store_true")
    args = parser.parse_args(argv)
    data = json.loads(args.catalog.read_text(encoding="utf-8"))
    products = validate_catalog(data)
    if args.check_downloads:
        check_downloads(products)
    print("validated %d products" % len(products))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print("catalog validation failed: %s" % error, file=sys.stderr)
        raise SystemExit(1)
