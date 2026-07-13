"""VettedMe infrastructure pre-flight — no Manus or live operations required."""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

DEFAULT_BASE = "http://127.0.0.1:8000"


def fetch_json(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=15) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    base = os.environ.get("VETTED_BASE_URL", DEFAULT_BASE).rstrip("/")
    print(f"VettedMe pre-flight — {base}\n")

    try:
        payload = fetch_json(f"{base}/health/vettedme")
    except urllib.error.URLError as exc:
        print(f"FAIL  API not reachable at {base}")
        print(f"      {exc}")
        print("\nStart VettedMe first: double-click VettedMe.ai on desktop")
        return 1

    overall = payload.get("status", "unknown")
    print(f"Overall: {overall}")
    print(f"Summary: {payload.get('summary', '')}\n")

    icon = {"pass": "OK  ", "warn": "WARN", "fail": "FAIL"}
    failed = 0
    for row in payload.get("checks", []):
        mark = icon.get(row.get("status"), "????")
        level = row.get("level", "required")
        print(f"[{mark}] {row.get('name')} ({level})")
        print(f"       {row.get('detail')}")
        if row.get("status") == "fail" and level == "required":
            failed += 1

    print()
    if failed:
        print(f"Result: NOT READY — {failed} required check(s) failed")
        return 1
    if overall == "infra_ready":
        print("Result: INFRA READY — platform ready for dev/testing (Manus not required)")
        return 0
    print("Result: review warnings above")
    return 0


if __name__ == "__main__":
    sys.exit(main())
