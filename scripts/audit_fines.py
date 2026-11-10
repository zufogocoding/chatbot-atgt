#!/usr/bin/env python3
"""Reconcile the consolidated fines with the provisions at their cited paths."""
from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from catalog_common import load_jsonl
from validate_catalog import normalize

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
RANGE = re.compile(r"từ\s+([\d.]+)(?:\s+đồng)?\s+đến\s+([\d.]+)\s+đồng", re.I)
CAP = re.compile(
    r"tối đa không vượt quá\s+([\d.]+)\s+đồng đối với chủ phương tiện là (cá nhân|tổ chức)",
    re.I,
)


def amounts(text: str) -> list[tuple[int, int]]:
    return [(int(low.replace(".", "")), int(high.replace(".", "")))
            for low, high in RANGE.findall(text)]


def caps(text: str) -> dict[str, int]:
    return {subject: int(value.replace(".", "")) for value, subject in CAP.findall(text)}


def audit() -> list[dict]:
    records = load_jsonl(DATA / "catalog/consolidated/violations.jsonl")
    provisions = load_jsonl(DATA / "parsed/168-provisions.jsonl")
    by_path = {(r["article"], str(r["clause"]), r["point"]): r["text"] for r in provisions}
    base_text = normalize((DATA / "parsed/168-2024-nd-cp-full.txt").read_text(encoding="utf-8"))
    amendment_text = normalize((DATA / "parsed/238-2026-nd-cp.txt").read_text(encoding="utf-8"))
    amendments = json.loads((DATA / "amendments/238-2026.json").read_text(encoding="utf-8"))
    added = {r["id"]: r for r in amendments["added"]}
    changed = {r["id"] for r in amendments["patches"]}
    results = []
    for record in records:
        rid = record["id"]
        basis = record["legal_basis"]
        article, clause, point = basis["article"], str(basis["clause"]), basis["point"]
        path = (article, clause, point)
        amendment_basis = ""
        if rid in added:
            # Records added by 238/2026 may inherit a fine range from the
            # original clause (11.e/13.e) or carry a new clause intro (9a).
            source = added[rid]
            clause_text = source.get("clause_text") or source["behavior_text"]
            behavior = source["behavior_text"]
            in_base = normalize(clause_text) in base_text
            in_amendment = normalize(clause_text) in amendment_text
            path_ok = normalize(behavior) in amendment_text and (in_base or in_amendment)
            path_ok = path_ok and basis["path"] == (
                f"{article}.{clause}" + (f".{point}" if point else "")
            )
            amount_basis = (
                f"168/2024/NĐ-CP Điều {article} khoản {clause}" if in_base
                else f"238/2026/NĐ-CP Điều 11 khoản 1"
            )
            amendment_basis = source.get("amendment_basis", "")
        else:
            clause_text = by_path.get((article, clause, None), "")
            behavior = by_path.get(path, "")
            path_ok = bool(clause_text and behavior) and normalize(clause_text) in base_text
            path_ok = path_ok and normalize(behavior) in base_text
            amount_basis = f"168/2024/NĐ-CP Điều {article} khoản {clause}"
            if rid in changed:
                amendment_basis = " | ".join(dict.fromkeys(
                    patch["source"] for patch in amendments["patches"] if patch["id"] == rid
                ))

        ranges = amounts(clause_text)
        if clause_text.startswith("Phạt cảnh cáo"):
            expected_kind, expected = "warning", (0, 0)
        elif clause_text.startswith("Tịch thu phương tiện"):
            expected_kind, expected = "additional_only", (None, None)
        else:
            expected_kind, expected = "fine", ranges[0] if ranges else (None, None)
            path_ok = path_ok and bool(ranges)
        expected_org = ranges[1] if article == 32 and len(ranges) > 1 else (None, None)
        expected_caps = caps(clause_text)
        org = record.get("fine_by_subject", {}).get("to_chuc", {})
        actual = (record["fine_min"], record["fine_max"])
        actual_org = (org.get("min"), org.get("max"))
        actual_cap = record.get("fine_cap")
        actual_org_cap = org.get("cap")
        passed = path_ok and record["record_kind"] == expected_kind
        passed = passed and expected == actual and expected_org == actual_org
        passed = passed and expected_caps.get("cá nhân") == actual_cap
        passed = passed and expected_caps.get("tổ chức") == actual_org_cap
        results.append(dict(
            id=rid, record_kind=record["record_kind"], legal_path=basis["path"],
            fine_min=actual[0], fine_max=actual[1],
            fine_unit=record.get("fine_unit"), fine_cap=actual_cap,
            expected_fine_min=expected[0], expected_fine_max=expected[1],
            expected_fine_cap=expected_caps.get("cá nhân"),
            fine_org_min=actual_org[0], fine_org_max=actual_org[1],
            fine_org_cap=actual_org_cap,
            expected_fine_org_min=expected_org[0], expected_fine_org_max=expected_org[1],
            expected_fine_org_cap=expected_caps.get("tổ chức"),
            amount_source=record["source_url"], amount_basis=amount_basis,
            amendment_basis=amendment_basis,
            amount_source_text=clause_text, audit_result="match" if passed else "mismatch",
        ))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, help="optional UTF-8 CSV report")
    args = parser.parse_args()
    rows = audit()
    if args.out:
        with args.out.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    failures = [row["id"] for row in rows if row["audit_result"] != "match"]
    print(f"Audited {len(rows)} records against cited provisions. Mismatches: {len(failures)}")
    for rid in failures:
        print(f"  {rid}")
    return int(bool(failures))


if __name__ == "__main__":
    raise SystemExit(main())
