#!/usr/bin/env python3
"""Apply Nghị định 238/2026/NĐ-CP amendments to the 168/2024 draft catalog.

This script is intentionally deterministic: every text patch is matched by its
exact old/new string, and the script fails loudly if a target record or source
phrase is missing. The output is the *consolidated* catalog in force from
15/08/2026.

Input : data/catalog/draft/violations-168.jsonl
        data/catalog/draft/penalty-rules-168.jsonl
        data/amendments/238-2026.json
Output: data/catalog/consolidated/violations.jsonl
        data/catalog/consolidated/penalty-rules.jsonl
        data/catalog/consolidated/summary.json
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
IN_VIOLATIONS = ROOT / "data/catalog/draft/violations-168.jsonl"
IN_RULES = ROOT / "data/catalog/draft/penalty-rules-168.jsonl"
AMENDMENTS = ROOT / "data/amendments/238-2026.json"
OUT_DIR = ROOT / "data/catalog/consolidated"
OUT_VIOLATIONS = OUT_DIR / "violations.jsonl"
OUT_RULES = OUT_DIR / "penalty-rules.jsonl"
OUT_SUMMARY = OUT_DIR / "summary.json"

AMENDMENT_DOC = "238/2026/NĐ-CP"
AMENDMENT_EFFECTIVE = "2026-08-15"
CONSOLIDATED_AS_OF = "2026-11-09"
DOC = "168/2024/NĐ-CP"
DOC_TITLE = (
    "Nghị định 168/2024/NĐ-CP quy định xử phạt vi phạm hành chính về trật tự, "
    "an toàn giao thông trong lĩnh vực giao thông đường bộ; trừ điểm, phục hồi "
    "điểm giấy phép lái xe (hợp nhất với Nghị định 238/2026/NĐ-CP)"
)
SOURCE_URL_AMENDMENT = "https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/7/238-ndcp.signed.pdf"

TEXT_FIELDS = ("behavior_text", "clause_text", "source_quote")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def dump_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def rebuild_source_quote(rec: dict[str, Any]) -> str:
    clause = rec.get("clause_text", "")
    behavior = rec.get("behavior_text", "")
    lb = rec.get("legal_basis", {})
    if lb.get("point") and clause and behavior and clause != behavior:
        return f"{clause} || {behavior}"
    return behavior or clause


def mark_amended(rec: dict[str, Any]) -> None:
    version = rec["version"]
    if AMENDMENT_DOC not in version["amended_by"]:
        version["amended_by"].append(AMENDMENT_DOC)
    version["effective_from"] = AMENDMENT_EFFECTIVE
    version["last_amended"] = AMENDMENT_EFFECTIVE
    rec["source_url_amendment"] = SOURCE_URL_AMENDMENT
    rec["verification"]["status"] = "draft"
    rec["verification"]["notes"] = (
        "Consolidated text after 238/2026/NĐ-CP; verify against both gazettes."
    )


def apply_patch(records: dict[str, dict[str, Any]], patch: dict[str, Any]) -> None:
    rid = patch["id"]
    if rid not in records:
        raise SystemExit(f"patch target not found: {rid}")
    rec = records[rid]
    op = patch["op"]

    if op == "replace":
        old, new = patch["old"], patch["new"]
        hit = False
        for field in TEXT_FIELDS:
            value = rec.get(field, "")
            if old in value:
                rec[field] = value.replace(old, new)
                hit = True
        if not hit:
            raise SystemExit(f"patch {rid}: old text not found in any field")
    elif op == "remove":
        old = patch["old"]
        hit = False
        for field in TEXT_FIELDS:
            value = rec.get(field, "")
            if old in value:
                rec[field] = value.replace(old, "")
                hit = True
        if not hit:
            raise SystemExit(f"remove patch {rid}: text not found in any field")
    elif op == "set_text":
        rec["behavior_text"] = patch["text"]
    else:
        raise SystemExit(f"patch {rid}: unsupported op {op!r}")

    rec["source_quote"] = rebuild_source_quote(rec)
    mark_amended(rec)


def add_record(records: dict[str, dict[str, Any]], added: dict[str, Any]) -> None:
    rid = added["id"]
    if rid in records:
        raise SystemExit(f"added record already exists: {rid}")
    rec = {
        "id": rid,
        "document": DOC,
        "document_title": DOC_TITLE,
        "article_title": added.get(
            "article_title",
            "Xử phạt, trừ điểm giấy phép lái xe của người điều khiển xe ô tô, "
            "xe chở người bốn bánh có gắn động cơ, xe chở hàng bốn bánh có gắn động cơ "
            "và các loại xe tương tự xe ô tô vi phạm quy tắc giao thông đường bộ",
        ),
        "vehicle_type": added["vehicle_type"],
        "subject": added.get("subject", "nguoi_dieu_khien"),
        "behavior_group": added["behavior_group"],
        "behavior_text": added["behavior_text"],
        "clause_text": added["behavior_text"],
        "fine_min": added["fine_min"],
        "fine_max": added["fine_max"],
        "fine_text": added["fine_text"],
        "record_kind": added["record_kind"],
        "additional_penalties": [],
        "remedial_measures": [],
        "license_points": 0,
        "license_points_condition": None,
        "penalty_rule_ids": [],
        "legal_basis": {**added["legal_basis"], "document": DOC},
        "source_url": SOURCE_URL_AMENDMENT,
        "source_url_amendment": SOURCE_URL_AMENDMENT,
        "source_quote": added["source_quote"],
        "verification": {
            "status": "draft",
            "verified_by": "",
            "verified_at": "",
            "notes": "New provision added by 238/2026/NĐ-CP Điều 2 khoản 1.",
        },
        "version": {
            "effective_from": AMENDMENT_EFFECTIVE,
            "effective_to": None,
            "amended_by": [AMENDMENT_DOC],
            "last_amended": AMENDMENT_EFFECTIVE,
            "consolidated_as_of": CONSOLIDATED_AS_OF,
        },
    }
    records[rid] = rec


def patch_rules(rules: dict[str, dict[str, Any]], patch: dict[str, Any]) -> None:
    rid = patch["id"]
    if rid not in rules:
        raise SystemExit(f"rule patch target not found: {rid}")
    rule = rules[rid]
    op = patch.get("op", "set_text")
    if op == "replace":
        old, new = patch.get("old", ""), patch.get("new", "")
        if old not in rule["text"]:
            raise SystemExit(f"rule patch {rid}: old text not found")
        rule["text"] = rule["text"].replace(old, new)
        if "description" in rule["penalty"]:
            rule["penalty"]["description"] = rule["penalty"]["description"].replace(old, new)
    elif "text" in patch:
        rule["text"] = patch["text"]
    elif op not in ("replace", "set_text"):
        raise SystemExit(f"rule patch {rid}: unsupported op {op!r}")
    if patch.get("remove_refs"):
        remove = {(r["clause"], r.get("point")) for r in patch["remove_refs"]}
        rule["refs"] = [
            r for r in rule.get("refs", [])
            if (r["clause"], r.get("point")) not in remove
        ]
    existing = {(r["clause"], r["point"]) for r in rule.get("refs", [])}
    for ref in patch.get("add_refs", []):
        key = (ref["clause"], ref.get("point"))
        if key not in existing:
            rule["refs"].append({"clause": ref["clause"], "point": ref.get("point")})
            existing.add(key)
    rule["amended_by"] = AMENDMENT_DOC
    rule["effective_from"] = AMENDMENT_EFFECTIVE
    rule["amendment_basis"] = patch["source"]
    rule["source_url_amendment"] = SOURCE_URL_AMENDMENT
    rule["source_quote_amendment"] = patch.get("source_quote", "")


def rule_matches(rec: dict[str, Any], rule: dict[str, Any], ref: dict[str, Any]) -> bool:
    lb = rec["legal_basis"]
    if rec["document"] != rule["document"]:
        return False
    if lb["article"] != rule["article"] or lb["clause"] != ref["clause"]:
        return False
    if ref.get("point") is not None and lb.get("point") != ref["point"]:
        return False
    return True


REMEDIAL_TYPES = {
    "bien_phap_khac_phuc",
    "thu_hoi_dang_ky_xe",
    "thu_hoi_ho_so",
}


def attach_penalties(records: list[dict[str, Any]], rules: list[dict[str, Any]]) -> None:
    """Recompute all sanctions from scratch so the result is idempotent."""
    for rec in records:
        base_confiscation = rec["record_kind"] == "additional_only"
        rec["additional_penalties"] = (
            [{"type": "tich_thu_phuong_tien", "condition": None}]
            if base_confiscation
            else []
        )
        rec["remedial_measures"] = []
        rec["license_points"] = 0
        rec["license_points_condition"] = None
        rec["penalty_rule_ids"] = []

    for rule in rules:
        penalty = rule["penalty"]
        for ref in rule["refs"]:
            for rec in records:
                if not rule_matches(rec, rule, ref):
                    continue
                if penalty["type"] == "tru_diem_gplx":
                    rec["license_points"] = max(rec["license_points"], penalty["points"])
                    if penalty.get("condition"):
                        rec["license_points_condition"] = penalty["condition"]
                elif penalty["type"] in REMEDIAL_TYPES:
                    if penalty not in rec["remedial_measures"]:
                        rec["remedial_measures"].append(penalty)
                else:
                    if penalty not in rec["additional_penalties"]:
                        rec["additional_penalties"].append(penalty)
                if rule["id"] not in rec["penalty_rule_ids"]:
                    rec["penalty_rule_ids"].append(rule["id"])


def clause_sort_key(clause: Any) -> tuple[int, float, str]:
    """Order numeric clauses, with inserted clauses like 1a before clause 1."""
    if isinstance(clause, int):
        return (0, float(clause), "")
    text = str(clause)
    m = re.fullmatch(r"(\d+)([a-zđ]?)", text)
    if not m:
        return (2, 0.0, text)
    number = int(m.group(1))
    suffix = m.group(2)
    if not suffix:
        return (0, float(number), "")
    # "1a" was inserted *before* clause 1 by 238/2026.
    offset = 0.5 + (ord(suffix) - ord("a")) / 100.0
    return (0, number - 1 + offset, suffix)


def sort_key(rec: dict[str, Any]):
    lb = rec["legal_basis"]
    return (lb["article"], clause_sort_key(lb["clause"]), lb.get("point") or "")


def main() -> None:
    amendments = json.loads(AMENDMENTS.read_text(encoding="utf-8"))
    violations = {r["id"]: r for r in load_jsonl(IN_VIOLATIONS)}
    rules = {r["id"]: r for r in load_jsonl(IN_RULES)}

    if len(violations) != len(load_jsonl(IN_VIOLATIONS)):
        raise SystemExit("duplicate violation ids in draft catalog")

    for patch in amendments.get("patches", []):
        apply_patch(violations, patch)
    for added in amendments.get("added", []):
        add_record(violations, added)
    for patch in amendments.get("rule_patches", []):
        patch_rules(rules, patch)

    records = sorted(violations.values(), key=sort_key)
    rule_list = sorted(rules.values(), key=lambda r: (r["article"], clause_sort_key(r["clause"]), r.get("point") or ""))

    amended_rules = {rule["id"] for rule in rule_list if rule.get("amended_by")}
    previously_affected = {rec["id"] for rec in records if amended_rules.intersection(rec["penalty_rule_ids"])}
    attach_penalties(records, rule_list)

    for rec in records:
        version = rec.setdefault("version", {})
        version.setdefault("amended_by", [])
        version["consolidated_as_of"] = CONSOLIDATED_AS_OF
        rec["document_title"] = DOC_TITLE
        if rec["id"] in previously_affected or amended_rules.intersection(rec["penalty_rule_ids"]):
            mark_amended(rec)

    dump_jsonl(OUT_VIOLATIONS, records)
    dump_jsonl(OUT_RULES, rule_list)

    summary = {
        "document": DOC,
        "consolidated_with": AMENDMENT_DOC,
        "consolidated_as_of": CONSOLIDATED_AS_OF,
        "amendment_effective_from": AMENDMENT_EFFECTIVE,
        "articles": sorted({r["legal_basis"]["article"] for r in records}),
        "violations": len(records),
        "by_article": {
            str(a): sum(1 for r in records if r["legal_basis"]["article"] == a)
            for a in sorted({r["legal_basis"]["article"] for r in records})
        },
        "by_vehicle": {
            v: sum(1 for r in records if r["vehicle_type"] == v)
            for v in ("xe_may", "o_to", "both")
        },
        "with_additional_penalty": sum(1 for r in records if r["additional_penalties"]),
        "with_remedial_measures": sum(1 for r in records if r["remedial_measures"]),
        "with_license_points": sum(1 for r in records if r["license_points"]),
        "penalty_rules": len(rule_list),
        "patched_records": len(amendments.get("patches", [])),
        "added_records": len(amendments.get("added", [])),
        "patched_rules": len(amendments.get("rule_patches", [])),
        "status": "draft",
    }
    OUT_SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
