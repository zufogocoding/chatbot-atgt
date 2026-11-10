#!/usr/bin/env python3
"""Export a short, risk-focused spot-check worksheet.

This is **not** the two-person verification gate. It gives one reviewer a
30-record sample of the highest-risk fine records so the project can report a
real human spot-check without reviewing all 259 fines. The sample covers:

* passenger records (Điều 12);
* records amended by 238/2026/NĐ-CP;
* organization fines;
* license-point conditions;
* additional penalties;
* remedial measures.

The selection is deterministic and round-robin across those groups. The
reviewer fills the same columns as the full worksheet, plus the pre-filled
``risk_reason`` column for context.

Run:
    python3 scripts/export_spotcheck.py
    python3 scripts/export_spotcheck.py --limit 20 --out /tmp/spotcheck.csv
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_common import load_jsonl  # noqa: E402
from export_review import FIELDS as REVIEW_FIELDS, clause_key, review_row  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VIOLATIONS = ROOT / "data/catalog/consolidated/violations.jsonl"
DEFAULT_OUT = ROOT / "data/catalog/review/spotcheck-2026-11-10.csv"
AMENDMENT = "238/2026/NĐ-CP"

RISKS: list[tuple[str, Callable[[dict[str, Any]], bool]]] = [
    ("người được chở", lambda rec: rec["subject"] == "nguoi_duoc_cho"),
    (
        "sửa đổi 238/2026",
        lambda rec: AMENDMENT in (rec.get("version", {}).get("amended_by") or []),
    ),
    (
        "phạt tổ chức",
        lambda rec: bool(rec.get("fine_by_subject", {}).get("to_chuc")),
    ),
    (
        "điều kiện trừ điểm GPLX",
        lambda rec: bool(rec.get("license_points_condition")),
    ),
    ("hình phạt bổ sung", lambda rec: bool(rec.get("additional_penalties"))),
    ("biện pháp khắc phục", lambda rec: bool(rec.get("remedial_measures"))),
]

FIELDS = [REVIEW_FIELDS[0], "risk_reason", *REVIEW_FIELDS[1:]]


def risk_reasons(rec: dict[str, Any]) -> list[str]:
    return [label for label, matches in RISKS if matches(rec)]


def select_records(records: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    """Pick a deterministic sample, one record per risk group per round."""
    buckets = {
        label: sorted((rec for rec in records if matches(rec)), key=lambda rec: rec["id"])
        for label, matches in RISKS
    }
    selected: list[dict[str, Any]] = []
    seen: set[str] = set()
    while len(selected) < limit:
        progressed = False
        for label, _ in RISKS:
            if len(selected) >= limit:
                break
            for rec in buckets[label]:
                if rec["id"] in seen:
                    continue
                selected.append(rec)
                seen.add(rec["id"])
                progressed = True
                break
        if not progressed:
            break
    selected.sort(
        key=lambda rec: (
            rec["legal_basis"]["article"],
            clause_key(rec["legal_basis"]["clause"]),
            rec["legal_basis"].get("point") or "",
            rec["id"],
        )
    )
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--limit", type=int, default=30)
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")

    records = [rec for rec in load_jsonl(VIOLATIONS) if rec["record_kind"] == "fine"]
    selected = select_records(records, args.limit)

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        for rec in selected:
            row = review_row(rec)
            row["risk_reason"] = "; ".join(risk_reasons(rec))
            writer.writerow(row)

    display_path = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    counts = Counter(reason for rec in selected for reason in risk_reasons(rec))
    print(f"wrote {display_path} ({len(selected)} rows)")
    for label, _ in RISKS:
        print(f"  {label}: {counts[label]}/{len(selected)}")
    print("Đây là mẫu spot-check một người, không tạo được snapshot verified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
