#!/usr/bin/env python3
"""Export a review worksheet (CSV) for manual verification against the gazette.

Every row contains the catalog values plus blank columns for the reviewer.
Open the file in Excel/LibreOffice with UTF-8, compare each row with the
Công báo, then fill:

    expected_fine_min, expected_fine_max, fine_ok, citation_ok, text_ok,
    reviewer, reviewed_at, note

Suggested values for the *_ok columns: OK / SAI / NA.

Run: python3 scripts/export_review.py
     python3 scripts/export_review.py --fine-only
"""
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_common import format_penalty, legal_path, load_jsonl  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VIOLATIONS = ROOT / "data/catalog/consolidated/violations.jsonl"
DEFAULT_OUT = ROOT / "data/catalog/review/review-2026-11-09.csv"

FIELDS = [
    "id",
    "record_kind",
    "vehicle_type",
    "article",
    "clause",
    "point",
    "legal_path",
    "behavior_text",
    "fine_text",
    "fine_min",
    "fine_max",
    "license_points",
    "additional_penalties",
    "remedial_measures",
    "source_quote",
    "verification_status",
    "expected_fine_min",
    "expected_fine_max",
    "fine_ok",
    "citation_ok",
    "text_ok",
    "reviewer",
    "reviewed_at",
    "note",
]


def clause_key(clause: Any) -> tuple[int, str]:
    text = str(clause)
    match = re.fullmatch(r"(\d+)([a-zđ]?)", text)
    if not match:
        return (10_000, text)
    return (int(match.group(1)), match.group(2))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fine-only", action="store_true")
    args = parser.parse_args()

    records = load_jsonl(VIOLATIONS)
    if args.fine_only:
        records = [r for r in records if r["record_kind"] == "fine"]

    out = args.out
    if args.fine_only and out == DEFAULT_OUT:
        out = out.with_name(out.stem + "-fine.csv")

    records.sort(
        key=lambda r: (
            r["legal_basis"]["article"],
            clause_key(r["legal_basis"]["clause"]),
            r["legal_basis"].get("point") or "",
        )
    )

    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for rec in records:
            basis = rec["legal_basis"]
            writer.writerow(
                {
                    "id": rec["id"],
                    "record_kind": rec["record_kind"],
                    "vehicle_type": rec["vehicle_type"],
                    "article": basis["article"],
                    "clause": basis["clause"],
                    "point": basis.get("point") or "",
                    "legal_path": legal_path(rec),
                    "behavior_text": rec["behavior_text"],
                    "fine_text": rec.get("fine_text") or "",
                    "fine_min": rec.get("fine_min") if rec.get("fine_min") is not None else "",
                    "fine_max": rec.get("fine_max") if rec.get("fine_max") is not None else "",
                    "license_points": rec.get("license_points", 0),
                    "additional_penalties": "; ".join(
                        format_penalty(p) for p in rec.get("additional_penalties", [])
                    ),
                    "remedial_measures": "; ".join(
                        format_penalty(p) for p in rec.get("remedial_measures", [])
                    ),
                    "source_quote": rec.get("source_quote", ""),
                    "verification_status": rec.get("verification", {}).get("status", ""),
                    "expected_fine_min": "",
                    "expected_fine_max": "",
                    "fine_ok": "",
                    "citation_ok": "",
                    "text_ok": "",
                    "reviewer": "",
                    "reviewed_at": "",
                    "note": "",
                }
            )

    print(f"wrote {out.relative_to(ROOT)} ({len(records)} rows)")
    print("review columns: expected_fine_min, expected_fine_max, fine_ok, citation_ok, text_ok, reviewer, reviewed_at, note")
    return 0


if __name__ == "__main__":
    sys.exit(main())
