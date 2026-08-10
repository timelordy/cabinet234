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
ARTIFACT_FORMATS = {"exe": ".exe", "zip": ".zip"}
EXPERIMENT_STATUSES = {"archived", "paused", "watching"}
EXPERIMENT_IDS = {
    "sectionmaker",
    "divor",
    "timka",
    "revit-mcp",
    "clash-detector",
    "ai-bcf",
    "pwall",
}
DOWNLOAD_PREFIX = "https://github.com/timelordy/cabinet234/releases/download/"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
EXPERIMENT_PERIOD_RE = re.compile(r"^\d{4}(?:–(?:\d{4}|н\.в\.))?$")


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
    artifact_format = artifact.get("format")
    if artifact_format not in ARTIFACT_FORMATS or int(artifact.get("sizeBytes", 0)) <= 0:
        raise ValueError("download artifact size or format is invalid")
    if not action["url"].lower().endswith(ARTIFACT_FORMATS[artifact_format]):
        raise ValueError("download URL extension does not match artifact format")
    if not SHA256_RE.fullmatch(str(artifact.get("sha256", ""))):
        raise ValueError("download artifact SHA-256 is invalid")


def validate_catalog(data: dict[str, Any]) -> list[dict[str, Any]]:
    if data.get("schemaVersion") != "4.0" or data.get("mode") != "live":
        raise ValueError("unsupported catalog contract")
    _require_text(data.get("generatedAt"), "generatedAt")
    experiments = data.get("experiments")
    products = data.get("products")
    if not isinstance(experiments, list):
        raise ValueError("experiments must be an array")
    if not isinstance(products, list):
        raise ValueError("products must be an array")
    ids: set[str] = set()
    experiment_ids: set[str] = set()
    expected_experiment_keys = {
        "id", "name", "direction", "context", "summary",
        "period", "status", "icon", "technologies",
    }
    for experiment in experiments:
        if not isinstance(experiment, dict) or set(experiment) != expected_experiment_keys:
            raise ValueError("experiment has an invalid public shape")
        experiment_id = _require_text(experiment.get("id"), "experiment.id")
        if experiment_id in ids:
            raise ValueError("duplicate catalog id: %s" % experiment_id)
        ids.add(experiment_id)
        experiment_ids.add(experiment_id)
        for field in ("name", "direction", "context", "summary", "period", "icon"):
            _require_text(experiment.get(field), "experiment.%s" % field)
        if not EXPERIMENT_PERIOD_RE.fullmatch(experiment["period"]):
            raise ValueError("%s has an invalid research period" % experiment_id)
        if experiment.get("status") not in EXPERIMENT_STATUSES:
            raise ValueError("%s has an invalid research status" % experiment_id)
        if experiment.get("icon") != "%s.png" % experiment_id:
            raise ValueError("%s has an invalid icon name" % experiment_id)
        technologies = experiment.get("technologies")
        if not isinstance(technologies, list) or not technologies:
            raise ValueError("%s must list technologies" % experiment_id)
        for technology in technologies:
            _require_text(technology, "experiment.technologies")
    if experiment_ids != EXPERIMENT_IDS:
        raise ValueError("experiment allowlist changed")
    for product in products:
        if not isinstance(product, dict):
            raise ValueError("product must be an object")
        product_id = _require_text(product.get("id"), "product.id")
        if product_id in ids:
            raise ValueError("duplicate catalog id: %s" % product_id)
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
