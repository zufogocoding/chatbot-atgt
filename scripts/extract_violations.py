#!/usr/bin/env python3
"""Extract violation candidates from Nghị định 168/2024/NĐ-CP.

Scope of this first pass:
  - Điều 6  : ô tô - quy tắc giao thông
  - Điều 7  : xe máy - quy tắc giao thông
  - Điều 12 : hành vi của người được chở trên xe máy/ô tô (mũ bảo hiểm,
              dây đai an toàn, bám kéo, che ô)
  - Điều 13 : ô tô - điều kiện phương tiện
  - Điều 14 : xe máy - điều kiện phương tiện
  - Điều 18 : điều kiện của người điều khiển xe cơ giới (cả hai loại xe)
  - Điều 32 : chủ phương tiện

The output is a *draft* catalog. Every record carries a source quote and a
legal path so a human can verify it against the original document.

Input : data/parsed/168-provisions.jsonl
Output: data/catalog/draft/violations-168.jsonl
        data/catalog/draft/penalty-rules-168.jsonl
        data/catalog/draft/summary-168.json
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any

from catalog_common import finalize_license_points, set_license_points

ROOT = Path(__file__).resolve().parents[1]
IN = ROOT / "data/parsed/168-provisions.jsonl"
OUT_VIOLATIONS = ROOT / "data/catalog/draft/violations-168.jsonl"
OUT_RULES = ROOT / "data/catalog/draft/penalty-rules-168.jsonl"
OUT_SUMMARY = ROOT / "data/catalog/draft/summary-168.json"
OVERRIDES = ROOT / "data/overrides/penalty-conditions.json"

DOC = "168/2024/NĐ-CP"
DOC_TITLE = (
    "Nghị định 168/2024/NĐ-CP quy định xử phạt vi phạm hành chính về trật tự, "
    "an toàn giao thông trong lĩnh vực giao thông đường bộ; trừ điểm, phục hồi "
    "điểm giấy phép lái xe"
)
SOURCE_URL = "https://datafiles.chinhphu.vn/cpp/files/vbpq/2025/01/168-nd-cp.signed.pdf"

ARTICLE_META = {
    6: {"vehicle_type": "o_to", "behavior_group": "quy_tac_giao_thong"},
    7: {"vehicle_type": "xe_may", "behavior_group": "quy_tac_giao_thong"},
    # Điều 12 mostly covers public-order violations, not vehicle operation.
    # Only the clauses about passengers on motorbikes/cars are in scope; see
    # ARTICLE_12_INCLUDE below.
    12: {"vehicle_type": "both", "behavior_group": "quy_tac_giao_thong"},
    13: {"vehicle_type": "o_to", "behavior_group": "dieu_kien_phuong_tien"},
    14: {"vehicle_type": "xe_may", "behavior_group": "dieu_kien_phuong_tien"},
    # Điều 18 covers driver conditions for both cars and motorbikes. The
    # concrete vehicle type is inferred from each point's wording.
    18: {"vehicle_type": "both", "behavior_group": "dieu_kien_nguoi_dieu_khien"},
    # Điều 32 covers the vehicle owner, not the driver. Clause-level vehicle
    # mapping is explicit because several clauses do not repeat the vehicle
    # name (e.g. clause 5/6 refer back to Điều 20 - cars).
    32: {"vehicle_type": "both", "behavior_group": "chu_phuong_tien"},
}

# Article 12 clauses worth cataloguing for a motorbike/car lookup tool:
#   2.d   : passenger on a motorbike uses an umbrella
#   4     : passenger in a car does not wear a seatbelt
#   5.a/b : passenger on a motorbike clings/stands or does not wear a helmet
# The rest of Article 12 is public-order regulation (sidewalk trading, drones,
# road obstructions...) and is outside this project's scope.
ARTICLE_12_INCLUDE = {(2, "d"), (4, None), (5, "a"), (5, "b")}

# Points added or repealed by 238/2026 are handled in
# data/amendments/238-2026.json, not in the base 168 extraction. Clause 9a and
# points 11.e/13.e do not exist in the 168 text, so they are added there.
#
# 238/2026 Điều 19 khoản 17 repeals points d, đ, e, g of Article 32 clause 17.
ARTICLE_32_SKIP_POINTS = {(17, "d"), (17, "đ"), (17, "e"), (17, "g")}

ARTICLE_32_VEHICLE = {
    1: "xe_may",
    2: "o_to",
    3: "xe_may",
    4: "xe_may",
    5: "o_to",
    6: "o_to",
    7: "o_to",
    8: "xe_may",
    9: "o_to",
    10: "xe_may",
    11: "o_to",
    12: "o_to",
    13: "o_to",
    14: "o_to",
    15: "o_to",
    16: "o_to",
    17: "both",
}

SUBJECT_BY_ARTICLE = {
    12: "nguoi_duoc_cho",
    32: "chu_phuong_tien",
}


def provision_in_scope(article: int, clause: int, point: str | None) -> bool:
    """Whether a clause/point belongs to this project's catalog scope."""
    if article == 12:
        if point is None:
            # Keep the clause intro (fine amount + subject) for clauses whose
            # points are included; drop unrelated clauses entirely.
            return clause in {2, 4, 5}
        return (clause, point) in ARTICLE_12_INCLUDE
    if article == 32:
        if (clause, point) in ARTICLE_32_SKIP_POINTS:
            return False
    return True


def subject_for(article: int) -> str:
    return SUBJECT_BY_ARTICLE.get(article, "nguoi_dieu_khien")

FINE_RE = re.compile(
    r"Phạt tiền từ\s+([\d\.]+)\s+đồng\s+đến\s+([\d\.]+)\s+đồng", re.IGNORECASE
)
# Some Article 32 clauses omit "đồng" after the first number, e.g.
# "từ 8.000.000 đến 12.000.000 đồng". This looser pattern is used only to
# find the second (organisation) range.
ANY_FINE_RE = re.compile(
    r"từ\s+([\d\.]+)\s*(?:đồng)?\s+đến\s+([\d\.]+)\s+đồng", re.IGNORECASE
)
WARNING_RE = re.compile(r"Phạt cảnh cáo", re.IGNORECASE)
CONFISCATE_RE = re.compile(r"Tịch thu phương tiện", re.IGNORECASE)
# Article 32 clauses 5/6 fine every extra passenger but cap the total:
# "... tổng mức phạt tiền tối đa không vượt quá 75.000.000 đồng đối với
# chủ phương tiện là cá nhân, ... 150.000.000 đồng ... là tổ chức".
FINE_CAP_RE = re.compile(
    r"tối đa không vượt quá\s+([\d\.]+)\s+đồng đối với chủ phương tiện là (cá nhân|tổ chức)",
    re.IGNORECASE,
)

# "điểm h, điểm i khoản 3; khoản 6; điểm a khoản 9"
REF_CLAUSE_RE = re.compile(r"khoản\s+(\d+)", re.IGNORECASE)
REF_POINT_RE = re.compile(r"điểm\s+([a-zđ])", re.IGNORECASE)

PENALTY_STARTS = (
    "Ngoài việc bị phạt tiền",
    "Ngoài việc bị áp dụng hình thức xử phạt",
)


def money(value: str) -> int:
    return int(value.replace(".", "").replace(",", ""))


def slug(text: str, max_len: int = 60) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9à-ỹđ]+", "-", text)
    return text.strip("-")[:max_len].strip("-")


def infer_vehicle_type(article: int, clause: int, text: str) -> str:
    """Resolve the vehicle type for articles that cover more than one type."""
    if article == 32:
        return ARTICLE_32_VEHICLE.get(clause, "both")
    default = ARTICLE_META[article]["vehicle_type"]
    if default != "both":
        return default
    lowered = text.lower()
    has_car = any(
        key in lowered
        for key in (
            "xe ô tô",
            "xe chở người bốn bánh",
            "xe chở hàng bốn bánh",
            "xe tương tự xe ô tô",
        )
    )
    has_bike = any(
        key in lowered
        for key in ("xe mô tô", "xe gắn máy", "xe tương tự xe mô tô")
    )
    if has_car and has_bike:
        return "both"
    if has_car:
        return "o_to"
    if has_bike:
        return "xe_may"
    return "both"


def load_provisions() -> list[dict[str, Any]]:
    with IN.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def is_penalty_rule(text: str) -> bool:
    return any(text.startswith(prefix) for prefix in PENALTY_STARTS)


def parse_refs(text: str) -> list[dict[str, Any]]:
    """Return [{'clause': int, 'point': str|None}, ...] from a rule sentence.

    The legal text lists references like:
      "điểm h, điểm i khoản 3; điểm a, điểm b khoản 4; khoản 6 Điều này"
    We pair each clause with the points that appear immediately before it.
    A single rule may contain multiple "quy định tại ... Điều này" blocks.
    """
    blocks = re.findall(
        r"quy định tại\s+(.*?)(?:\s+Điều này|\s+bị\s+|\s+còn bị\s+|$)", text
    )
    refs: list[dict[str, Any]] = []
    for ref_text in blocks:
        clause_matches = list(REF_CLAUSE_RE.finditer(ref_text))
        previous_end = 0
        for cm in clause_matches:
            clause = int(cm.group(1))
            prefix = ref_text[previous_end : cm.start()]
            points = [p.lower() for p in REF_POINT_RE.findall(prefix)]
            if points:
                for point in points:
                    refs.append({"clause": clause, "point": point})
            else:
                refs.append({"clause": clause, "point": None})
            previous_end = cm.end()

    seen = set()
    unique = []
    for ref in refs:
        key = (ref["clause"], ref["point"])
        if key not in seen:
            seen.add(key)
            unique.append(ref)
    return unique


def extract_description(text: str, marker: str) -> str | None:
    lowered = text.lower()
    index = lowered.find(marker)
    if index < 0:
        return None
    description = text[index + len(marker) :].strip().rstrip(";.")
    return description or None


def parse_penalty(text: str) -> dict[str, Any] | None:
    """Parse the sanction part of a rule sentence."""
    if "trừ điểm giấy phép lái xe" in text:
        m = re.search(
            r"trừ điểm giấy phép lái xe.{0,180}?(\d+)\s+điểm", text, re.IGNORECASE
        )
        if m:
            penalty: dict[str, Any] = {
                "type": "tru_diem_gplx",
                "points": int(m.group(1)),
            }
            # Keep the full condition, not only "chủ phương tiện là người
            # trực tiếp điều khiển". Clauses 5/6 have two point tiers whose
            # conditions differ by the percentage of extra passengers.
            condition = re.search(
                r"(chủ phương tiện là người trực tiếp điều khiển phương tiện.*?)"
                r"(?:,\s*)?còn bị trừ điểm giấy phép lái xe",
                text,
                re.IGNORECASE,
            )
            if condition:
                penalty["condition"] = condition.group(1).strip().rstrip(",")
            return penalty
    if "tước quyền sử dụng giấy phép lái xe" in text:
        m = re.search(
            r"tước quyền sử dụng giấy phép lái xe\s+từ\s+(\d+)\s+tháng\s+đến\s+(\d+)\s+tháng",
            text,
        )
        if m:
            return {
                "type": "tuoc_gplx",
                "min_months": int(m.group(1)),
                "max_months": int(m.group(2)),
            }
        m = re.search(
            r"tước quyền sử dụng giấy phép lái xe\s+(\d+)\s+tháng", text
        )
        if m:
            return {
                "type": "tuoc_gplx",
                "min_months": int(m.group(1)),
                "max_months": int(m.group(1)),
            }
    if "tước quyền sử dụng giấy chứng nhận kiểm định" in text.lower():
        m = re.search(
            r"tước quyền sử dụng giấy chứng nhận kiểm định.{0,160}?"
            r"từ\s+(\d+)\s+tháng\s+đến\s+(\d+)\s+tháng",
            text,
            re.IGNORECASE,
        )
        if m:
            return {
                "type": "tuoc_giay_kiem_dinh",
                "min_months": int(m.group(1)),
                "max_months": int(m.group(2)),
            }
    if "tước quyền sử dụng phù hiệu" in text.lower():
        m = re.search(
            r"tước quyền sử dụng phù hiệu.{0,120}?"
            r"từ\s+(\d+)\s+tháng\s+đến\s+(\d+)\s+tháng",
            text,
            re.IGNORECASE,
        )
        if m:
            return {
                "type": "tuoc_phu_hieu",
                "min_months": int(m.group(1)),
                "max_months": int(m.group(2)),
            }
    # Remedial measures can contain an exception such as "(trừ trường hợp
    # bị tịch thu phương tiện)", so check "buộc" before confiscation.
    if text.lstrip().startswith("Buộc") or " buộc " in text:
        return {
            "type": "bien_phap_khac_phuc",
            "description": extract_description(text, "buộc "),
        }
    if "phải khôi phục" in text.lower():
        description = extract_description(text, "phải khôi phục lại ")
        if description:
            description = f"khôi phục lại {description}"
        return {
            "type": "bien_phap_khac_phuc",
            "description": description,
        }
    if "tịch thu biển số" in text.lower():
        return {"type": "tich_thu_bien_so"}
    if "tịch thu phương tiện" in text.lower():
        penalty = {"type": "tich_thu_phuong_tien", "condition": None}
        m = re.search(
            r"trong trường hợp (.+?) thì bị tịch thu phương tiện", text, re.IGNORECASE
        )
        if m:
            penalty["condition"] = m.group(1).strip()
        return penalty
    if "tịch thu thiết bị" in text:
        return {"type": "tich_thu_thiet_bi"}
    if "thu hồi giấy phép lái xe" in text:
        return {"type": "thu_hoi_gplx"}
    if "thu hồi hồ sơ đăng ký xe" in text:
        return {
            "type": "thu_hoi_ho_so",
            "description": extract_description(text, "bị thu hồi "),
        }
    if "thu hồi chứng nhận đăng ký xe" in text:
        return {
            "type": "thu_hoi_dang_ky_xe",
            "description": extract_description(text, "bị thu hồi "),
        }
    return None


def ref_in_scope(article: int, ref: dict[str, Any]) -> bool:
    return provision_in_scope(article, ref["clause"], ref.get("point"))


def parse_penalty_rules(provisions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rules: list[dict[str, Any]] = []
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for p in provisions:
        if p["article"] in ARTICLE_META:
            if not provision_in_scope(p["article"], p["clause"], p["point"]):
                continue
            grouped[(p["article"], p["clause"])].append(p)

    for (article, clause), items in grouped.items():
        clause_row = next((x for x in items if x["point"] is None), None)
        points = [x for x in items if x["point"] is not None]
        # A penalty-rule clause is identified by its clause intro, not by the
        # point text: points under it start with "Thực hiện hành vi...".
        if clause_row is None or not is_penalty_rule(clause_row["text"]):
            continue
        rows = points if points else [clause_row]
        for row in rows:
            penalty = parse_penalty(row["text"])
            refs = [ref for ref in parse_refs(row["text"]) if ref_in_scope(article, ref)]
            if not penalty or not refs:
                continue
            rules.append(
                {
                    "id": f"nd168-d{article}-k{clause}"
                    + (f"-{row['point']}" if row["point"] else ""),
                    "document": DOC,
                    "article": article,
                    "clause": clause,
                    "point": row["point"],
                    "text": row["text"],
                    "refs": refs,
                    "penalty": penalty,
                }
            )
    return rules


def apply_penalty_conditions(rules: list[dict[str, Any]]) -> None:
    if not OVERRIDES.exists():
        return
    conditions = json.loads(OVERRIDES.read_text(encoding="utf-8")).get("conditions", {})
    for rule in rules:
        condition = conditions.get(rule["id"])
        if condition:
            rule["penalty"]["condition"] = condition


def extract_violations(
    provisions: list[dict[str, Any]], rules: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    by_key: dict[tuple[int, int, str | None], dict[str, Any]] = {}
    # Group by article/clause so points can inherit the clause intro and fine.
    grouped: dict[tuple[int, int], list[dict[str, Any]]] = defaultdict(list)
    for p in provisions:
        if p["article"] not in ARTICLE_META:
            continue
        if not provision_in_scope(p["article"], p["clause"], p["point"]):
            continue
        grouped[(p["article"], p["clause"])].append(p)

    for (article, clause), items in grouped.items():
        clause_row = next((x for x in items if x["point"] is None), None)
        points = [x for x in items if x["point"] is not None]
        base = clause_row or (points[0] if points else None)
        if base is None:
            continue

        text = base["text"]
        fine = FINE_RE.search(text)
        warning = WARNING_RE.search(text)
        confiscate = CONFISCATE_RE.search(text)

        fine_min = fine_max = None
        record_kind = "fine"
        if fine:
            fine_min, fine_max = money(fine.group(1)), money(fine.group(2))
        elif warning:
            fine_min = fine_max = 0
            record_kind = "warning"
        elif confiscate:
            fine_min = fine_max = None
            record_kind = "additional_only"
        else:
            # Penalty rule clause (Ngoài việc...) or a clause without a fine.
            continue

        fine_unit = fine_cap = None
        fine_by_subject = None
        if article == 32:
            ranges = ANY_FINE_RE.findall(text)
            if len(ranges) >= 2:
                fine_by_subject = {
                    "to_chuc": {
                        "min": money(ranges[1][0]),
                        "max": money(ranges[1][1]),
                    }
                }
            if "trên mỗi người vượt quá" in text.lower():
                caps = {
                    subject: money(value)
                    for value, subject in FINE_CAP_RE.findall(text)
                }
                fine_unit = "per_person"
                fine_cap = caps.get("cá nhân")
                if fine_by_subject and caps.get("tổ chức"):
                    fine_by_subject["to_chuc"]["cap"] = caps["tổ chức"]

        # Clauses 5/6 put the per-person fine and cap before the behaviour.
        # Keep source_quote intact but show the citizen only the actual act.
        display_text = text
        if article == 32 and clause in (5, 6):
            marker = "đối với chủ phương tiện là tổ chức"
            index = text.lower().find(marker)
            if index >= 0:
                display_text = text[index + len(marker) :].strip()
                display_text = display_text[0].upper() + display_text[1:]

        def make_record(row: dict[str, Any]) -> dict[str, Any]:
            path = f"{article}.{clause}" + (f".{row['point']}" if row["point"] else "")
            rec_id = "nd168-d{}-k{}".format(article, clause) + (
                f"-{row['point']}" if row["point"] else ""
            )
            behavior = row["text"] if row["point"] else display_text
            record = {
                "id": rec_id,
                "document": DOC,
                "document_title": DOC_TITLE,
                "article_title": base["article_title"],
                "vehicle_type": (
                    "o_to" if path == "32.17.b"
                    else infer_vehicle_type(article, clause, f"{text} {behavior}")
                ),
                "subject": subject_for(article),
                "behavior_group": ARTICLE_META[article]["behavior_group"],
                "behavior_text": behavior,
                "clause_text": text,
                "fine_min": fine_min,
                "fine_max": fine_max,
                "fine_text": fine.group(0) if fine else ("Phạt cảnh cáo" if warning else ""),
                "record_kind": record_kind,
                "additional_penalties": [],
                "remedial_measures": [],
                "license_points": 0,
                "license_points_condition": None,
                "license_point_tiers": [],
                "penalty_rule_ids": [],
                "legal_basis": {
                    "document": DOC,
                    "article": article,
                    "clause": clause,
                    "point": row["point"],
                    "path": path,
                },
                "source_url": SOURCE_URL,
                "source_quote": text if not row["point"] else f"{text} || {row['text']}",
                "verification": {
                    "status": "draft",
                    "verified_by": "",
                    "verified_at": "",
                    "notes": "Auto-extracted; verify amount and citation against the gazette.",
                },
                "version": {
                    "effective_from": "2026-01-01" if path == "6.3.m" else "2025-01-01",
                    "effective_to": None,
                    "amended_by": [],
                },
            }
            if fine_unit:
                record["fine_unit"] = fine_unit
                record["fine_cap"] = fine_cap
            if fine_by_subject:
                record["fine_by_subject"] = fine_by_subject
            return record

        if points:
            for row in points:
                rec = make_record(row)
                if confiscate:
                    rec["additional_penalties"].append(
                        {"type": "tich_thu_phuong_tien", "condition": None}
                    )
                by_key[(article, clause, row["point"])] = rec
        else:
            rec = make_record(base)
            if confiscate:
                rec["additional_penalties"].append(
                    {"type": "tich_thu_phuong_tien", "condition": None}
                )
            by_key[(article, clause, None)] = rec

    # Attach penalty rules to matching records.
    records = list(by_key.values())
    for rule in rules:
        for ref in rule["refs"]:
            for rec in records:
                lb = rec["legal_basis"]
                if rec["document"] != rule["document"]:
                    continue
                if lb["article"] != rule["article"] or lb["clause"] != ref["clause"]:
                    continue
                if ref["point"] is not None and lb["point"] != ref["point"]:
                    continue
                if ref["point"] is None and lb["point"] is not None:
                    # A clause-level reference applies to every point in the clause.
                    pass
                penalty = rule["penalty"]
                if penalty["type"] == "tru_diem_gplx":
                    set_license_points(rec, penalty["points"], penalty.get("condition"))
                elif penalty["type"] in ("bien_phap_khac_phuc", "thu_hoi_dang_ky_xe"):
                    if penalty not in rec["remedial_measures"]:
                        rec["remedial_measures"].append(penalty)
                else:
                    if penalty not in rec["additional_penalties"]:
                        rec["additional_penalties"].append(penalty)
                if rule["id"] not in rec["penalty_rule_ids"]:
                    rec["penalty_rule_ids"].append(rule["id"])

    for rec in records:
        finalize_license_points(rec)

    # Stable order: article, clause, point.
    def sort_key(rec: dict[str, Any]):
        lb = rec["legal_basis"]
        return (lb["article"], lb["clause"], lb["point"] or "")

    return sorted(records, key=sort_key)


def main() -> None:
    provisions = load_provisions()
    rules = parse_penalty_rules(provisions)
    apply_penalty_conditions(rules)
    violations = extract_violations(provisions, rules)

    OUT_VIOLATIONS.parent.mkdir(parents=True, exist_ok=True)
    with OUT_VIOLATIONS.open("w", encoding="utf-8") as f:
        for rec in violations:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    with OUT_RULES.open("w", encoding="utf-8") as f:
        for rule in rules:
            f.write(json.dumps(rule, ensure_ascii=False) + "\n")

    summary = {
        "document": DOC,
        "articles": sorted(ARTICLE_META),
        "violations": len(violations),
        "by_article": {
            str(a): sum(1 for r in violations if r["legal_basis"]["article"] == a)
            for a in sorted(ARTICLE_META)
        },
        "by_vehicle": {
            v: sum(1 for r in violations if r["vehicle_type"] == v)
            for v in ("xe_may", "o_to", "both")
        },
        "with_additional_penalty": sum(
            1 for r in violations if r["additional_penalties"]
        ),
        "with_remedial_measures": sum(
            1 for r in violations if r["remedial_measures"]
        ),
        "with_license_points": sum(1 for r in violations if r["license_points"]),
        "penalty_rules": len(rules),
        "status": "draft",
    }
    OUT_SUMMARY.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
