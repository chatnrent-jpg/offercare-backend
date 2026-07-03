"""Quick live check: portal build stamp and open-shifts resilience markers."""

from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.main import PORTAL_BUILD_ID  # noqa: E402

BASE = "http://127.0.0.1:8000"
EXPECTED_BUILD = PORTAL_BUILD_ID


def main() -> int:
    ok = True
    try:
        portal = requests.get(f"{BASE}/portal/", timeout=10)
        js = requests.get(f"{BASE}/portal/app.js", timeout=10)
        shifts_js = requests.get(f"{BASE}/portal/shifts.js", timeout=10)
        health = requests.get(f"{BASE}/health/vettedcare", timeout=10)
    except requests.RequestException as exc:
        print(f"FAIL: API not reachable at {BASE} — {exc}")
        return 1

    build = portal.headers.get("X-Portal-Build", "")
    print("X-Portal-Build:", build or "(missing)")
    if build != EXPECTED_BUILD:
        print(f"WARN: expected {EXPECTED_BUILD} — restart API from repo root (start-api.bat)")
        ok = False

    bootstrap_idx = js.text.find("bootstrapDemoShifts")
    load_idx = js.text.find("loadShifts().catch")
    checks = {
        'id="app" in portal HTML': 'id="app"' in portal.text,
        "isAuthError in app.js": "isAuthError" in js.text,
        "open-shifts primary path": "/api/clinicians/me/open-shifts" in js.text,
        "shifts.js demo hints": "applyDemoClientLockHints" in shifts_js.text,
        "bootstrap before loadShifts": bootstrap_idx != -1 and load_idx != -1 and bootstrap_idx < load_idx,
        "API_TIMEOUT_MS": "API_TIMEOUT_MS" in js.text,
        "purgeStalePortalCache": "purgeStalePortalCache" in js.text,
        "lock confirm modal": "lock-confirm-modal" in portal.text and "showLockConfirmModal" in js.text,
    }
    for label, passed in checks.items():
        status = "OK" if passed else "FAIL"
        print(f"{status}: {label}")
        ok = ok and passed

    print("health:", health.status_code)
    open_shifts = requests.get(f"{BASE}/api/shifts/open?limit=3", timeout=15)
    print("GET /api/shifts/open:", open_shifts.status_code, f"rows={len(open_shifts.json()) if open_shifts.ok else 0}")

    if ok:
        print("PASS: portal live checks")
        return 0
    print("FAIL: portal live checks — hard refresh browser (Ctrl+Shift+R) after API restart")
    return 1


if __name__ == "__main__":
    sys.exit(main())
