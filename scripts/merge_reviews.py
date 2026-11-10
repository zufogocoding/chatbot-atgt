#!/usr/bin/env python3
"""Merge two independent manual review worksheets into a verified snapshot.

The catalog only moves to ``verified`` when two different reviewers confirm the
fine range, the legal citation and the behavior text for every record. This
script enforces that rule mechanically:

* both CSV files must cover exactly the same record IDs as the catalog;
* the reviewer names must be present and different;
* the catalog columns in each worksheet must still match the current catalog,
  so a reviewer can only fill the review columns;
* every required check must be ``OK`` in both files;
* the amounts typed by both reviewers must match the catalog.

If anything disagrees, no snapshot is written. On success, the script writes a
copy of the catalog with ``verification.status = "verified"`` and a JSON report
that records who checked which snapshot.

Run:
    python3 scripts/merge_reviews.py \
        --reviewer-a data/catalog/review/nguoi-ra-soat-1.csv \
        --reviewer-b data/catalog/review/nguoi-ra-soat-2.csv \
        --out data/catalog/verified/violations-2026-11-09.jsonl
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from catalog_common import format_penalty, legal_path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/catalog/consolidated/violations.jsonl"
VALID_CHECKS = {"OK", "SAI", "NA"}
CATALOG_COLUMNS = (
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
)
NUMERIC_COLUMNS = {"article", "fine_min", "fine_max", "license_points"}


def load_catalog(path: Path) -> list[dict[str, Any]]:
    records = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                records.append(json.loads(line))
    ids = [record["id"] for record in records]
    duplicates = [rid for rid, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate catalog ids: {duplicates}")
    return records


def load_review(path: Path) -> dict[str, dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path}: empty review worksheet")
    if "id" not in rows[0]:
        raise ValueError(f"{path}: missing id column")
    reviews: dict[str, dict[str, str]] = {}
    for row in rows:
        rid = (row.get("id") or "").strip()
        if not rid:
            raise ValueError(f"{path}: row without id")
        if rid in reviews:
            raise ValueError(f"{path}: duplicate id {rid}")
        reviews[rid] = row
    return reviews


def parse_amount(value: str, field: str, rid: str, path: Path) -> int:
    text = (value or "").strip().replace(".", "").replace(",", "")
    if not text:
        raise ValueError(f"{path}: {rid}: missing {field}")
    try:
        return int(text)
    except ValueError as error:
        raise ValueError(f"{path}: {rid}: {field} is not an integer: {value!r}") from error


def parse_date(value: str, rid: str, path: Path) -> date:
    text = (value or "").strip()
    if not text:
        raise ValueError(f"{path}: {rid}: missing reviewed_at")
    try:
        return date.fromisoformat(text[:10])
    except ValueError as error:
        raise ValueError(f"{path}: {rid}: invalid reviewed_at {value!r}") from error


def expected_cell(record: dict[str, Any], field: str) -> Any:
    basis = record.get("legal_basis") or {}
    if field == "record_kind":
        return record.get("record_kind")
    if field == "vehicle_type":
        return record.get("vehicle_type")
    if field == "article":
        return basis.get("article", record.get("article"))
    if field == "clause":
        return basis.get("clause", record.get("clause"))
    if field == "point":
        return basis.get("point") or ""
    if field == "legal_path":
        return legal_path(record)
    if field == "behavior_text":
        return record.get("behavior_text")
    if field == "fine_text":
        return record.get("fine_text") or ""
    if field == "fine_min":
        return record.get("fine_min")
    if field == "fine_max":
        return record.get("fine_max")
    if field == "license_points":
        return record.get("license_points", 0)
    if field == "additional_penalties":
        return "; ".join(format_penalty(p) for p in record.get("additional_penalties", []))
    if field == "remedial_measures":
        return "; ".join(format_penalty(p) for p in record.get("remedial_measures", []))
    if field == "source_quote":
        return record.get("source_quote", "")
    if field == "verification_status":
        return record.get("verification", {}).get("status", "")
    raise KeyError(field)


def same_cell(field: str, actual: str, expected: Any) -> bool:
    actual_text = (actual or "").replace("\r\n", "\n").strip()
    expected_text = ("" if expected is None else str(expected)).replace("\r\n", "\n").strip()
    if field in NUMERIC_COLUMNS:
        def number(text: str) -> int | None:
            cleaned = text.replace(".", "").replace(",", "").strip()
            try:
                return int(cleaned)
            except ValueError:
                return None

        actual_number, expected_number = number(actual_text), number(expected_text)
        if actual_number is not None and expected_number is not None:
            return actual_number == expected_number
    return actual_text == expected_text


def check_catalog_columns(
    record: dict[str, Any],
    row: dict[str, str],
    path: Path,
    errors: list[str],
) -> None:
    """Reject a worksheet that edited catalog cells instead of only reviewing them."""
    rid = record["id"]
    for field in CATALOG_COLUMNS:
        if field not in row:
            continue
        expected = expected_cell(record, field)
        if expected is None:
            continue
        actual = row.get(field, "")
        if not same_cell(field, actual, expected):
            errors.append(
                f"{path}: {rid}: catalog column {field} was modified; "
                "re-export the worksheet instead of editing catalog cells"
            )


def check_row(
    record: dict[str, Any],
    row: dict[str, str],
    path: Path,
    label: str,
    errors: list[str],
) -> str | None:
    rid = record["id"]
    check_catalog_columns(record, row, path, errors)
    reviewer = (row.get("reviewer") or "").strip()
    if not reviewer:
        errors.append(f"{path}: {rid}: missing reviewer")
    try:
        parse_date(row.get("reviewed_at", ""), rid, path)
    except ValueError as error:
        errors.append(str(error))

    for field in ("fine_ok", "citation_ok", "text_ok"):
        value = (row.get(field) or "").strip().upper()
        if value not in VALID_CHECKS:
            errors.append(f"{path}: {rid}: {field} must be OK, SAI or NA (got {value!r})")
            continue
        required = field in {"citation_ok", "text_ok"} or record.get("fine_min") is not None
        if required and value != "OK":
            errors.append(f"{path}: {rid}: {field} is {value or 'blank'}, expected OK ({label})")
        if not required and value == "OK":
            errors.append(f"{path}: {rid}: {field} should be NA because the record has no fine")

    if record.get("fine_min") is not None:
        for side in ("min", "max"):
            field = f"expected_fine_{side}"
            try:
                actual = parse_amount(row.get(field, ""), field, rid, path)
            except ValueError as error:
                errors.append(str(error))
                continue
            expected = record.get(f"fine_{side}")
            if actual != expected:
                errors.append(
                    f"{path}: {rid}: {field}={actual} but catalog has {expected}"
                )
    elif (row.get("expected_fine_min") or "").strip() or (row.get("expected_fine_max") or "").strip():
        errors.append(f"{path}: {rid}: expected_fine_* must be blank for a non-fine record")

    return reviewer or None


def merge(
    catalog: list[dict[str, Any]],
    review_a: dict[str, dict[str, str]],
    review_b: dict[str, dict[str, str]],
    path_a: Path,
    path_b: Path,
    fine_only: bool = False,
) -> tuple[list[dict[str, Any]], list[str], list[str], str]:
    errors: list[str] = []
    catalog_ids = {record["id"] for record in catalog}
    required_ids = {
        record["id"] for record in catalog
        if not fine_only or record.get("record_kind") == "fine"
    }
    for path, reviews in ((path_a, review_a), (path_b, review_b)):
        missing = sorted(required_ids - set(reviews))
        extra = sorted(set(reviews) - catalog_ids)
        if missing:
            errors.append(f"{path}: missing {len(missing)} records: {missing[:10]}")
        if extra:
            errors.append(f"{path}: unknown {len(extra)} records: {extra[:10]}")

    reviewers: dict[str, str] = {}
    for path, reviews, label in ((path_a, review_a, "A"), (path_b, review_b, "B")):
        names = {(row.get("reviewer") or "").strip() for row in reviews.values()}
        names.discard("")
        if len(names) > 1:
            errors.append(f"{path}: multiple reviewers in one worksheet: {sorted(names)}")
        reviewers[label] = next(iter(names), "")

    if reviewers["A"] and reviewers["A"].casefold() == reviewers["B"].casefold():
        errors.append("reviewer A and reviewer B must be different people")

    verified: list[dict[str, Any]] = []
    pending = 0
    for record in catalog:
        rid = record["id"]
        row_a, row_b = review_a.get(rid), review_b.get(rid)
        if row_a is None or row_b is None:
            if rid in required_ids:
                continue
            pending += 1
            verified.append(record)
            continue
        name_a = check_row(record, row_a, path_a, "A", errors)
        name_b = check_row(record, row_b, path_b, "B", errors)
        if name_a and name_b and name_a.casefold() == name_b.casefold():
            errors.append(f"{path_a}: {rid}: both worksheets name {name_a!r}")
        merged = dict(record)
        merged["verification"] = {
            "status": "verified",
            "verified_by": " + ".join(sorted({name_a or reviewers["A"], name_b or reviewers["B"]})),
            "verified_at": max(
                (row_a.get("reviewed_at") or "")[:10],
                (row_b.get("reviewed_at") or "")[:10],
            ),
            "notes": record.get("verification", {}).get("notes", ""),
        }
        verified.append(merged)

    if errors:
        return [], errors, [], ""

    checked = [record for record in verified if record["verification"]["status"] == "verified"]
    verified_at = max(record["verification"]["verified_at"] for record in checked)
    verified_by = sorted({record["verification"]["verified_by"] for record in checked})
    if pending:
        print(
            f"note: {pending} record(s) outside the fine-review scope stay draft",
            file=sys.stderr,
        )
    return verified, [], verified_by, verified_at


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path, default=CATALOG)
    parser.add_argument("--reviewer-a", type=Path, required=True)
    parser.add_argument("--reviewer-b", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--fine-only",
        action="store_true",
        help="only require the fine records; copy warnings/additional-only records at draft",
    )
    args = parser.parse_args()

    try:
        catalog = load_catalog(args.catalog)
        review_a = load_review(args.reviewer_a)
        review_b = load_review(args.reviewer_b)
    except (OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 1

    verified, errors, verified_by, verified_at = merge(
        catalog, review_a, review_b, args.reviewer_a, args.reviewer_b, args.fine_only
    )
    if errors:
        print(f"review merge failed with {len(errors)} problem(s):", file=sys.stderr)
        for error in errors[:50]:
            print(f"  {error}", file=sys.stderr)
        if len(errors) > 50:
            print(f"  ... and {len(errors) - 50} more", file=sys.stderr)
        return 1

    out = args.out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", encoding="utf-8") as handle:
        for record in verified:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    snapshot = verified[0]["version"]["consolidated_as_of"]
    report = {
        "snapshot": snapshot,
        "records": len(verified),
        "scope": "fine" if args.fine_only else "all",
        "verified_records": sum(1 for r in verified if r["verification"]["status"] == "verified"),
        "draft_records": sum(1 for r in verified if r["verification"]["status"] != "verified"),
        "verified_by": verified_by,
        "verified_at": verified_at,
        "reviewer_a": str(args.reviewer_a),
        "reviewer_b": str(args.reviewer_b),
    }
    report_path = args.report or out.with_suffix(".report.json")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"verified {len(verified)} records -> {out}")
    print(f"report -> {report_path}")
    print(f"reviewers: {', '.join(verified_by)}; reviewed at: {verified_at}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
