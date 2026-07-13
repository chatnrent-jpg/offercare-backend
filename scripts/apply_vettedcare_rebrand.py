"""One-shot VettedMe → VettedMe rebrand (paths + user-facing strings)."""

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
    text = text.replace("C:\\OFFERCARE.AI", "C:\\VettedMe.ai")
    text = text.replace("C:/VettedMe.ai", "C:/VettedMe.ai")
    text = text.replace("C:\\VettedMe.ai", "C:\\VettedMe.ai")
    text = text.replace("C:/VettedMe.ai", "C:/VettedMe.ai")
    text = text.replace("vettedme-backend", "vettedme-backend")
    text = text.replace("VettedMe.ai", "VettedMe.ai")
    text = re.sub(r"VettedMe(?!JobOffer)", "VettedMe", text)
    text = text.replace("vettedme_clinician_token", "vettedme_clinician_token")
    text = text.replace("vettedme_install_dismissed", "vettedme_install_dismissed")
    text = text.replace("vettedme-open-shifts.ics", "vettedme-open-shifts.ics")
    text = text.replace("vettedme-matched-shifts.ics", "vettedme-matched-shifts.ics")
    text = text.replace("vettedme-placements.ics", "vettedme-placements.ics")
    text = text.replace("vettedme-portal-v1", "vettedme-portal-v1")
    text = text.replace("container_name: vettedme-api", "container_name: vettedme-api")
    text = text.replace("container_name: vettedme-db", "container_name: vettedme-db")
    return text


def main() -> int:
    changed = 0
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in EXTS and path.name not in {".env.example", ".env.vettedme.example"}:
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
