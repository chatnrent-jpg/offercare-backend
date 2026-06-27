"""One-shot VettedCare → VettedCare rebrand (paths + user-facing strings)."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "__pycache__", ".git", ".pytest_cache", "node_modules"}
EXTS = {
    ".py",
    ".md",
    ".html",
    ".json",
    ".ps1",
    ".bat",
    ".yml",
    ".yaml",
    ".ini",
    ".txt",
    ".js",
    ".env.example",
    ".example",
}


def transform(text: str) -> str:
    text = text.replace("C:\\OFFERCARE.AI", "C:\\VettedCare.ai")
    text = text.replace("C:/VettedCare.ai", "C:/VettedCare.ai")
    text = text.replace("C:\\VettedCare.ai", "C:\\VettedCare.ai")
    text = text.replace("C:/VettedCare.ai", "C:/VettedCare.ai")
    text = text.replace("vettedcare-backend", "vettedcare-backend")
    text = text.replace("VettedCare.ai", "VettedCare.ai")
    text = re.sub(r"VettedCare(?!JobOffer)", "VettedCare", text)
    text = text.replace("vettedcare_clinician_token", "vettedcare_clinician_token")
    text = text.replace("vettedcare_install_dismissed", "vettedcare_install_dismissed")
    text = text.replace("vettedcare-open-shifts.ics", "vettedcare-open-shifts.ics")
    text = text.replace("vettedcare-matched-shifts.ics", "vettedcare-matched-shifts.ics")
    text = text.replace("vettedcare-placements.ics", "vettedcare-placements.ics")
    text = text.replace("vettedcare-portal-v1", "vettedcare-portal-v1")
    text = text.replace("container_name: vettedcare-api", "container_name: vettedcare-api")
    text = text.replace("container_name: vettedcare-db", "container_name: vettedcare-db")
    return text


def main() -> int:
    changed = 0
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in EXTS and path.name not in {".env.example", ".env.vettedcare.example"}:
            continue
        original = path.read_text(encoding="utf-8")
        updated = transform(original)
        if updated != original:
            path.write_text(updated, encoding="utf-8")
            changed += 1
            print(f"updated: {path.relative_to(ROOT)}")
    print(f"\nDone — {changed} file(s) updated.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
