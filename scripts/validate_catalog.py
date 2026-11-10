#!/usr/bin/env python3
"""Validate the consolidated violation catalog against its legal sources.

Checks are split into errors (must fix before publishing) and warnings
(need a human look but do not block the build).

Run: python3 scripts/validate_catalog.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "data/catalog/consolidated"
VIOLATIONS = CATALOG / "violations.jsonl"
RULES = CATALOG / "penalty-rules.jsonl"
SOURCE_168 = ROOT / "data/parsed/168-2024-nd-cp-full.txt"
SOURCE_238 = ROOT / "data/parsed/238-2026-nd-cp.txt"

VALID_PENALTY_TYPES = {
    "tru_diem_gplx",
    "tuoc_gplx",
    "tich_thu_phuong_tien",
    "tich_thu_thiet_bi",
    "tich_thu_bien_so",
    "tuoc_giay_kiem_dinh",
    "tuoc_phu_hieu",
    "thu_hoi_dang_ky_xe",
    "thu_hoi_gplx",
    "thu_hoi_ho_so",
    "bien_phap_khac_phuc",
}
VALID_LICENSE_POINTS = {0, 2, 3, 4, 6, 8, 10, 12}
VALID_VEHICLE_TYPES = {"xe_may", "o_to", "both"}
VALID_SUBJECTS = {"nguoi_dieu_khien", "chu_phuong_tien", "nguoi_duoc_cho"}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def normalize(text: str) -> str:
    text = text.replace("\u00a0", " ").replace("“", '"').replace("”", '"')
    text = text.replace("–", "-").replace("—", "-")
    text = re.sub(
        r"(?:\b\d{1,4}\s+)?công báo/số\s+\d+(?:\s*\+\s*\d+)?"
        r"/ngày\s+\d{2}-\d{2}-\d{4}(?:\s+\d{1,4})?",
        " ",
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"\s+", " ", text)
    return text.strip().lower()


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    records = load_jsonl(VIOLATIONS)
    rules = load_jsonl(RULES)
    source_168 = normalize(SOURCE_168.read_text(encoding="utf-8"))
    source_238 = normalize(SOURCE_238.read_text(encoding="utf-8"))
    amendments = json.loads((ROOT / "data/amendments/238-2026.json").read_text(encoding="utf-8"))
    patches_by_record: dict[str, list[dict[str, Any]]] = {}
    for patch in amendments.get("patches", []):
        patches_by_record.setdefault(patch["id"], []).append(patch)
    added_ids = {item["id"] for item in amendments.get("added", [])}

    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        dupes = sorted({x for x in ids if ids.count(x) > 1})
        errors.append(f"duplicate record ids: {dupes}")

    rule_ids = [r["id"] for r in rules]
    if len(rule_ids) != len(set(rule_ids)):
        dupes = sorted({x for x in rule_ids if rule_ids.count(x) > 1})
        errors.append(f"duplicate rule ids: {dupes}")

    rule_by_id = {r["id"]: r for r in rules}
    referenced_rule_ids: set[str] = set()

    fine_checked = 0
    quote_checked = 0
    for rec in records:
        rid = rec["id"]
        lb = rec["legal_basis"]

        if rec.get("vehicle_type") not in VALID_VEHICLE_TYPES:
            errors.append(f"{rid}: invalid vehicle_type {rec.get('vehicle_type')!r}")
        if rec.get("subject") not in VALID_SUBJECTS:
            errors.append(f"{rid}: invalid subject {rec.get('subject')!r}")
        if lb["article"] == 12 and rec.get("subject") != "nguoi_duoc_cho":
            errors.append(f"{rid}: Article 12 record must be a passenger")
        if lb["article"] == 32 and rec.get("subject") != "chu_phuong_tien":
            errors.append(f"{rid}: Article 32 record must be a vehicle owner")

        # 1. Fine range
        fmin, fmax = rec.get("fine_min"), rec.get("fine_max")
        if rec["record_kind"] == "fine":
            fine_checked += 1
            if fmin is None or fmax is None:
                errors.append(f"{rid}: fine record missing amount")
            elif fmin > fmax:
                errors.append(f"{rid}: fine_min {fmin} > fine_max {fmax}")
            elif fmin <= 0:
                errors.append(f"{rid}: fine record has non-positive minimum {fmin}")
        elif rec["record_kind"] == "warning":
            if fmin != 0 or fmax != 0:
                errors.append(f"{rid}: warning record must have fine 0")
        elif rec["record_kind"] == "additional_only":
            if fmin is not None or fmax is not None:
                errors.append(f"{rid}: additional-only record must have null fine")
        else:
            errors.append(f"{rid}: unknown record_kind {rec['record_kind']!r}")

        # 2. Citation path
        expected_path = f"{lb['article']}.{lb['clause']}" + (
            f".{lb['point']}" if lb.get("point") else ""
        )
        if lb.get("path") != expected_path:
            errors.append(f"{rid}: path {lb.get('path')} != {expected_path}")
        if lb.get("document") != "168/2024/NĐ-CP":
            errors.append(f"{rid}: unexpected legal document {lb.get('document')!r}")
        if not rec.get("source_quote", "").strip():
            errors.append(f"{rid}: empty source_quote")

        # 3. Source quote appears in the gazette text (after whitespace
        # normalization). Amended behavior texts may live in either document.
        quote_checked += 1
        behavior = normalize(rec.get("behavior_text", ""))
        clause = normalize(rec.get("clause_text", ""))
        if clause and clause not in source_168 and clause not in source_238:
            errors.append(f"{rid}: clause_text not found in 168 or 238 text")

        if rid in added_ids:
            if behavior not in source_238:
                errors.append(f"{rid}: added behavior_text not found in 238 text")
        elif rid in patches_by_record:
            reconstructed = behavior
            has_set_text = False
            has_removal = False
            for patch in patches_by_record[rid]:
                if patch["op"] == "replace":
                    raw_new = patch.get("new", "")
                    new = normalize(raw_new)
                    old = normalize(patch["old"])
                    if raw_new == "":
                        has_removal = True
                        if old in behavior:
                            errors.append(f"{rid}: removed text still present")
                        continue
                    if new not in reconstructed:
                        errors.append(f"{rid}: patch new text not applied")
                        continue
                    reconstructed = reconstructed.replace(new, old)
                elif patch["op"] == "set_text":
                    has_set_text = True
                    expected = normalize(patch["text"])
                    if behavior != expected:
                        errors.append(f"{rid}: set_text patch not applied")
                    if expected not in source_238:
                        errors.append(f"{rid}: set_text text not found in 238")
            if not has_set_text and not has_removal and reconstructed not in source_168:
                errors.append(
                    f"{rid}: behavior_text (reverse-patched) not found in 168 text"
                )
        elif behavior and behavior not in source_168:
            errors.append(f"{rid}: behavior_text not found in 168 text")

        # 4. Sanctions
        for penalty in rec.get("additional_penalties", []):
            if penalty.get("type") not in VALID_PENALTY_TYPES:
                errors.append(f"{rid}: invalid additional penalty {penalty!r}")
            if penalty.get("type") == "tuoc_gplx":
                if penalty["min_months"] > penalty["max_months"]:
                    errors.append(f"{rid}: suspension min > max")
        for measure in rec.get("remedial_measures", []):
            if measure.get("type") not in VALID_PENALTY_TYPES:
                errors.append(f"{rid}: invalid remedial measure {measure!r}")
        if rec.get("license_points") not in VALID_LICENSE_POINTS:
            errors.append(f"{rid}: invalid license points {rec.get('license_points')!r}")
        for penalty in rec.get("additional_penalties", []):
            if penalty.get("type") == "tich_thu_phuong_tien" and "condition" not in penalty:
                errors.append(
                    f"{rid}: confiscation penalty missing condition field"
                )

        for rule_id in rec.get("penalty_rule_ids", []):
            referenced_rule_ids.add(rule_id)
            if rule_id not in rule_by_id:
                errors.append(f"{rid}: dangling penalty_rule_id {rule_id}")

        # 5. Version metadata
        version = rec.get("version", {})
        if not version.get("consolidated_as_of"):
            errors.append(f"{rid}: missing consolidated_as_of")

    # 6. Every rule reference must resolve to at least one record.
    for rule in rules:
        for ref in rule.get("refs", []):
            matches = [
                r
                for r in records
                if r["legal_basis"]["article"] == rule["article"]
                and r["legal_basis"]["clause"] == ref["clause"]
                and (
                    ref.get("point") is None
                    or r["legal_basis"].get("point") == ref["point"]
                )
            ]
            if not matches:
                errors.append(
                    f"{rule['id']}: reference {ref['clause']}.{ref.get('point') or '*'}"
                    " does not resolve to a record"
                )

    unattached_rules = sorted(set(rule_by_id) - referenced_rule_ids)
    if unattached_rules:
        warnings.append(f"rules not attached to any record: {unattached_rules}")

    # 7. Known-good spot checks (citizen-facing high-traffic cases).
    by_id = {r["id"]: r for r in records}
    spot_checks = {
        "nd168-d6-k9-b": {
            "fine_min": 18_000_000,
            "fine_max": 20_000_000,
            "license_points": 4,
            "additional_penalties": [],
        },
        "nd168-d6-k6-a": {
            "fine_min": 6_000_000,
            "fine_max": 8_000_000,
            "license_points": 4,
        },
        "nd168-d6-k12": {
            "fine_min": 40_000_000,
            "fine_max": 50_000_000,
            "additional_penalties": [
                {"type": "tuoc_gplx", "min_months": 10, "max_months": 12}
            ],
        },
        "nd168-d6-k1a": {"fine_min": 0, "fine_max": 0, "record_kind": "warning"},
        "nd168-d12-k5-b": {
            "fine_min": 400_000,
            "fine_max": 600_000,
            "vehicle_type": "xe_may",
            "subject": "nguoi_duoc_cho",
        },
        "nd168-d12-k4": {
            "fine_min": 350_000,
            "fine_max": 400_000,
            "vehicle_type": "o_to",
            "subject": "nguoi_duoc_cho",
        },
        "nd168-d32-k3-a": {
            "fine_min": 800_000,
            "fine_max": 1_000_000,
            "vehicle_type": "xe_may",
            "subject": "chu_phuong_tien",
        },
        "nd168-d32-k7-h": {
            "fine_min": 4_000_000,
            "fine_max": 6_000_000,
            "vehicle_type": "o_to",
            "subject": "chu_phuong_tien",
        },
        "nd168-d32-k14-i": {
            "fine_min": 28_000_000,
            "fine_max": 30_000_000,
            "vehicle_type": "o_to",
        },
    }
    for rid, expected in spot_checks.items():
        rec = by_id.get(rid)
        if rec is None:
            errors.append(f"spot check: missing {rid}")
            continue
        for field, value in expected.items():
            if rec.get(field) != value:
                errors.append(
                    f"spot check {rid}: {field} is {rec.get(field)!r}, expected {value!r}"
                )

    # 8. Alias catalog must point at real records with matching vehicle types.
    alias_path = ROOT / "data/catalog/aliases.json"
    if alias_path.exists():
        aliases = json.loads(alias_path.read_text(encoding="utf-8"))
        alias_ids: set[str] = set()
        phrase_owner: dict[str, str] = {}
        referenced: set[str] = set()
        for entry in aliases.get("aliases", []):
            aid = entry.get("id", "")
            if not aid:
                errors.append("alias entry missing id")
                continue
            if aid in alias_ids:
                errors.append(f"duplicate alias id {aid}")
            alias_ids.add(aid)
            if not entry.get("canonical", "").strip():
                errors.append(f"alias {aid}: missing canonical text")
            for phrase in entry.get("citizen_phrases", []):
                key = normalize(phrase)
                if not key:
                    errors.append(f"alias {aid}: empty phrase")
                    continue
                if key in phrase_owner and phrase_owner[key] != aid:
                    warnings.append(
                        f"alias phrase {phrase!r} appears in both "
                        f"{phrase_owner[key]} and {aid}"
                    )
                phrase_owner[key] = aid
            for vehicle, items in entry.get("records", {}).items():
                if vehicle not in VALID_VEHICLE_TYPES:
                    errors.append(f"alias {aid}: invalid vehicle key {vehicle!r}")
                    continue
                if len(items) > 1 and any(not x.get("qualifier") for x in items):
                    errors.append(
                        f"alias {aid}/{vehicle}: multiple records need qualifiers"
                    )
                for item in items:
                    rid = item.get("record_id")
                    rec = by_id.get(rid)
                    if rec is None:
                        errors.append(f"alias {aid}: unknown record {rid!r}")
                        continue
                    if rec["vehicle_type"] not in (vehicle, "both"):
                        errors.append(
                            f"alias {aid}: record {rid} is {rec['vehicle_type']}, "
                            f"mapped under {vehicle}"
                        )
                    referenced.add(rid)
        unmatched = sorted(set(by_id) - referenced)
        if unmatched:
            warnings.append(
                f"{len(unmatched)} records have no citizen alias: {unmatched[:8]}"
            )

    # 9. Amended records must not retain superseded wording.
    superseded_phrases = [
        "chở người trên nóc xe",
        "để người đu bám ở cửa xe, bên ngoài thành xe",
        "giấy chứng nhận kiểm định",
    ]
    for rec in records:
        blob = normalize(
            " ".join(
                str(rec.get(k, ""))
                for k in ("behavior_text", "clause_text", "source_quote")
            )
        )
        for phrase in superseded_phrases:
            if phrase in blob:
                errors.append(f"{rec['id']}: retains superseded phrase {phrase!r}")

    print(f"records: {len(records)}")
    print(f"penalty rules: {len(rules)}")
    print(f"fine records checked: {fine_checked}")
    print(f"source quotes checked: {quote_checked}")
    print(f"errors: {len(errors)}")
    print(f"warnings: {len(warnings)}")
    for err in errors:
        print(f"  ERROR   {err}")
    for warn in warnings:
        print(f"  WARNING {warn}")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
