#!/usr/bin/env python3
"""Query the local SQLite catalog from the command line.

Examples:
    python3 scripts/query_catalog.py search "xe máy vượt đèn đỏ"
    python3 scripts/query_catalog.py search "nồng độ cồn" --vehicle o_to
    python3 scripts/query_catalog.py record nd168-d7-k7-c
    python3 scripts/query_catalog.py answer "xe máy vượt đèn đỏ"
    python3 scripts/query_catalog.py answer "ô tô quá tốc độ"
    python3 scripts/query_catalog.py procedure "hạn khiếu nại quyết định xử phạt"
    python3 scripts/query_catalog.py stats

This is a development/inspection tool. The FastAPI service will reuse the same
database and matching rules.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_common import (  # noqa: E402
    format_penalty,
    format_range,
    legal_path,
    normalize_text,
    tokens,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = ROOT / "data/build/catalog.db"

VEHICLE_LABELS = {"xe_may": "Xe máy", "o_to": "Ô tô", "both": "Cả hai loại xe"}

# Generic question words only. "không" is meaningful and must be kept.
STOPWORDS = {
    "bi",
    "phat",
    "bao",
    "nhieu",
    "tien",
    "la",
    "gi",
    "the",
    "nao",
    "toi",
    "muon",
    "hoi",
    "cho",
    "cua",
    "khi",
    "va",
    "thi",
    "phai",
    "ra",
    "sao",
    "duoc",
    "nhu",
    "co",
    "vay",
    "a",
    "nhi",
}

CAR_RE = re.compile(r"\b(?:o to|oto|xe hoi|bon banh|4 banh)\b")
BIKE_RE = re.compile(r"\b(?:xe may|xemay|mo to|xe gan may|hai banh|2 banh)\b")


def open_db(path: Path) -> sqlite3.Connection:
    if not path.exists():
        raise SystemExit(f"database not found: {path}\nrun: python3 scripts/build_db.py")
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def detect_vehicle(query_ascii: str) -> str | None:
    car = bool(CAR_RE.search(query_ascii))
    bike = bool(BIKE_RE.search(query_ascii))
    if car and not bike:
        return "o_to"
    if bike and not car:
        return "xe_may"
    return None


def parse_record(row: sqlite3.Row) -> dict[str, Any]:
    rec = dict(row)
    for field in ("additional_penalties", "remedial_measures", "penalty_rule_ids", "amended_by"):
        if field in rec and isinstance(rec[field], str):
            rec[field] = json.loads(rec[field])
    return rec


def get_record(con: sqlite3.Connection, record_id: str) -> dict[str, Any] | None:
    row = con.execute("SELECT * FROM violations WHERE id = ?", (record_id,)).fetchone()
    return parse_record(row) if row else None


def find_aliases(con: sqlite3.Connection, query_ascii: str) -> list[dict[str, Any]]:
    """Longest alias phrase contained in the question wins."""
    rows = con.execute(
        """
        SELECT g.id, g.canonical, g.requires_qualifier, g.notes,
               p.phrase, p.phrase_ascii
        FROM alias_phrases p
        JOIN alias_groups g ON g.id = p.alias_id
        WHERE length(p.phrase_ascii) >= 4
          AND ? LIKE '%' || p.phrase_ascii || '%'
        ORDER BY length(p.phrase_ascii) DESC, g.id
        """,
        (query_ascii,),
    ).fetchall()

    found: list[dict[str, Any]] = []
    seen: set[str] = set()
    for row in rows:
        if row["id"] in seen:
            continue
        seen.add(row["id"])
        found.append(dict(row))
    return found


def alias_record_ids(con: sqlite3.Connection, alias_id: str, vehicle: str | None) -> list[dict[str, Any]]:
    sql = """
        SELECT ar.record_id, ar.vehicle_type, ar.qualifier, v.fine_min, v.fine_max,
               v.license_points, v.article, v.clause, v.point, v.legal_path
        FROM alias_records ar
        JOIN violations v ON v.id = ar.record_id
        WHERE ar.alias_id = ?
    """
    params: list[Any] = [alias_id]
    if vehicle:
        sql += " AND (ar.vehicle_type = ? OR ar.vehicle_type = 'both')"
        params.append(vehicle)
    sql += " ORDER BY v.fine_min IS NULL, v.fine_min, v.id"
    return [dict(r) for r in con.execute(sql, params).fetchall()]


def corpus_idf(con: sqlite3.Connection) -> tuple[int, Counter[str]]:
    rows = con.execute("SELECT behavior_ascii, clause_ascii FROM violations").fetchall()
    df: Counter[str] = Counter()
    for row in rows:
        for token in set((row[0] + " " + row[1]).split()):
            df[token] += 1
    return len(rows), df


def fts_search(con: sqlite3.Connection, query: str, vehicle: str | None, limit: int) -> list[dict[str, Any]]:
    terms = [t for t in tokens(query) if len(t) > 1 and t not in STOPWORDS]
    if not terms:
        return []
    match = " OR ".join(terms)
    sql = """
        SELECT v.*, bm25(violations_fts) AS score
        FROM violations_fts
        JOIN violations v ON v.id = violations_fts.id
        WHERE violations_fts MATCH ?
    """
    params: list[Any] = [match]
    if vehicle:
        sql += " AND (v.vehicle_type = ? OR v.vehicle_type = 'both')"
        params.append(vehicle)
    sql += " ORDER BY score LIMIT ?"
    params.append(max(limit * 5, 25))
    candidates = [parse_record(r) for r in con.execute(sql, params).fetchall()]

    # FTS5 OR-matching lets one common token ("không") pull in unrelated
    # records. Keep candidates whose IDF-weighted token coverage is high.
    total_docs, df = corpus_idf(con)
    term_set = set(terms)

    def idf(token: str) -> float:
        return math.log((total_docs + 1) / (df.get(token, 0) + 1)) + 1

    query_weight = sum(idf(t) for t in term_set)
    if not query_weight:
        return []
    kept: list[dict[str, Any]] = []
    for rec in candidates:
        doc_tokens = set((rec["behavior_ascii"] + " " + rec["clause_ascii"]).split())
        matched = term_set & doc_tokens
        if len(matched) < min(2, len(term_set)):
            continue
        if len(term_set) <= 3 and len(matched) < len(term_set):
            continue
        coverage = sum(idf(t) for t in matched) / query_weight
        if coverage < 0.70:
            continue
        rec["coverage"] = coverage
        kept.append(rec)
        if len(kept) >= limit:
            break
    return kept


def short(text: str, limit: int = 150) -> str:
    text = " ".join(text.split()).rstrip(";")
    return text if len(text) <= limit else text[: limit - 1] + "…"


def search_procedures(con: sqlite3.Connection, question: str, limit: int) -> list[sqlite3.Row]:
    terms = dict.fromkeys(term for term in tokens(question) if term not in STOPWORDS)
    if not terms:
        return []
    return con.execute(
        """
        SELECT p.id, p.topic, p.title, p.text, p.as_of
        FROM procedures_fts
        JOIN procedures p ON p.id = procedures_fts.id
        WHERE procedures_fts MATCH ?
        ORDER BY bm25(procedures_fts, 0, 4, 3, 1), p.id
        LIMIT ?
        """,
        (" OR ".join(terms), limit),
    ).fetchall()


def cmd_procedure(con: sqlite3.Connection, args: argparse.Namespace) -> int:
    if args.limit < 1:
        raise SystemExit("--limit phải từ 1 trở lên")
    if not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'procedures_fts'").fetchone():
        raise SystemExit("Cần dựng lại SQLite bằng scripts/build_db.py để tra thủ tục.")
    results = search_procedures(con, args.query, args.limit)
    if not results:
        print("Không tìm thấy đoạn thủ tục phù hợp.")
        return 0
    for result in results:
        print(f"## {result['title']} ({result['id']})")
        print(result["text"])
        citations = con.execute(
            """
            SELECT s.number, c.locator, s.url
            FROM procedure_citations c JOIN procedure_sources s ON s.id = c.source_id
            WHERE c.procedure_id = ? ORDER BY c.position
            """,
            (result["id"],),
        )
        for citation in citations:
            print(f"- {citation['number']} · {citation['locator']} · {citation['url']}")
        print()
    return 0


def format_date(value: str | None) -> str:
    if not value:
        return ""
    parts = value.split("-")
    if len(parts) == 3:
        return "/".join(reversed(parts))
    return value


def vehicle_or_all(rec: dict[str, Any]) -> str:
    return VEHICLE_LABELS.get(rec["vehicle_type"], rec["vehicle_type"])


def print_search_results(results: list[dict[str, Any]], show_score: bool = False) -> None:
    for index, rec in enumerate(results, 1):
        extra = []
        if rec["record_kind"] == "warning":
            extra.append("cảnh cáo")
        elif rec["record_kind"] == "additional_only":
            extra.append("không phạt tiền")
        else:
            extra.append(format_range(rec["fine_min"], rec["fine_max"]))
        if rec["license_points"]:
            extra.append(f"trừ {rec['license_points']} điểm")
        if rec["additional_penalties"]:
            extra.append(", ".join(format_penalty(p) for p in rec["additional_penalties"]))
        score = f" score={rec.get('score'):.2f}" if show_score and "score" in rec else ""
        print(f"{index}. {rec['id']} | {vehicle_or_all(rec)} | {' | '.join(extra)}{score}")
        print(f"   {legal_path(rec)} — {short(rec['behavior_text'])}")


def cmd_search(con: sqlite3.Connection, args: argparse.Namespace) -> int:
    query_ascii = normalize_text(args.query)
    vehicle = args.vehicle or detect_vehicle(query_ascii)

    aliases = find_aliases(con, query_ascii)
    for alias in aliases:
        records = alias_record_ids(con, alias["id"], vehicle)
        if records:
            print(f"Khớp alias: {alias['id']} — {alias['canonical']}")
            if alias.get("requires_qualifier"):
                print("  (cần hỏi thêm để chọn đúng khung)")
            for item in records:
                record = get_record(con, item["record_id"])
                if record:
                    qualifier = f" [{item['qualifier']}]" if item["qualifier"] else ""
                    details = format_range(record["fine_min"], record["fine_max"])
                    if record["license_points"]:
                        details += f" | trừ {record['license_points']} điểm"
                    if record["additional_penalties"]:
                        details += " | " + ", ".join(
                            format_penalty(p) for p in record["additional_penalties"]
                        )
                    print(
                        f"  - {record['id']} | {vehicle_or_all(record)} | "
                        f"{details}{qualifier}"
                    )
                    print(f"    {legal_path(record)} — {short(record['behavior_text'])}")
            return 0

    results = fts_search(con, args.query, vehicle, args.limit)
    if not results:
        print("Không tìm thấy bản ghi phù hợp.")
        return 0
    print_search_results(results, show_score=args.show_score)
    return 0


SUBJECT_LABELS = {
    "chu_phuong_tien": "Chủ phương tiện",
    "nguoi_dieu_khien": "Người điều khiển",
    "nguoi_duoc_cho": "Người được chở",
}


def print_answer(rec: dict[str, Any], full_quote: bool = False, title: str | None = None) -> None:
    print(f"## {title or short(rec['behavior_text'], 180)}")
    print()
    print(f"- Loại xe: {vehicle_or_all(rec)}")
    subject = rec.get("subject")
    if subject and subject != "nguoi_dieu_khien":
        print(f"- Đối tượng bị xử phạt: {SUBJECT_LABELS.get(subject, subject)}")
    if rec["record_kind"] == "warning":
        print("- Mức phạt: Phạt cảnh cáo")
    elif rec["record_kind"] == "additional_only":
        print("- Mức phạt tiền: Không có")
    else:
        fine = format_range(rec["fine_min"], rec["fine_max"])
        org_min, org_max = rec.get("fine_org_min"), rec.get("fine_org_max")
        if org_min is not None and org_max is not None:
            print(f"- Mức phạt (cá nhân): {fine}")
            print(f"- Mức phạt (tổ chức): {format_range(org_min, org_max)}")
        else:
            print(f"- Mức phạt: {fine}")

    if rec["additional_penalties"]:
        print("- Hình phạt bổ sung:")
        for penalty in rec["additional_penalties"]:
            print(f"  - {format_penalty(penalty)}")
    else:
        print("- Hình phạt bổ sung: Không")

    if rec["license_points"]:
        condition = rec.get("license_points_condition")
        if condition:
            print(
                f"- Trừ điểm GPLX: {rec['license_points']} điểm "
                f"(nếu {condition})"
            )
        else:
            print(f"- Trừ điểm GPLX: {rec['license_points']} điểm")
    else:
        print("- Trừ điểm GPLX: Không")

    if rec["remedial_measures"]:
        print("- Biện pháp khắc phục hậu quả:")
        for measure in rec["remedial_measures"]:
            print(f"  - {format_penalty(measure)}")

    print(f"- Căn cứ: {legal_path(rec)} — {rec['document']}")
    version = format_date(rec.get("consolidated_as_of"))
    amended = rec.get("amended_by") or []
    if amended:
        print(f"  (đã sửa đổi bởi {', '.join(amended)}; hợp nhất đến {version})")
    elif version:
        print(f"  (hợp nhất đến {version})")

    quote = (rec.get("source_quote") or "").replace(" || ", " — ")
    if full_quote:
        print(f"- Trích dẫn: {quote}")
    else:
        print(f"- Trích dẫn: {short(quote, 400)}")

    print()
    print(
        "Lưu ý: Thông tin tham khảo, không thay thế tư vấn pháp lý. "
        "Lệnh này chỉ tra cứu mức phạt."
    )


def cmd_record(con: sqlite3.Connection, args: argparse.Namespace) -> int:
    rec = get_record(con, args.record_id)
    if rec is None:
        print(f"Không tìm thấy record: {args.record_id}", file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(rec, ensure_ascii=False, indent=2))
    else:
        print_answer(rec, full_quote=True)
    return 0


def explain_clarification(alias: dict[str, Any], items: list[dict[str, Any]]) -> None:
    print(f"## {alias['canonical']}")
    print()
    print("Cần thêm thông tin để chọn đúng khung phạt:")
    for index, item in enumerate(items, 1):
        qualifier = item["qualifier"] or "trường hợp này"
        path = legal_path(item)
        print(
            f"{index}. {qualifier}: "
            f"{format_range(item['fine_min'], item['fine_max'])} "
            f"({path})"
        )
    if alias.get("notes"):
        print()
        print(f"Ghi chú: {alias['notes']}")


def cmd_answer(con: sqlite3.Connection, args: argparse.Namespace) -> int:
    if args.record:
        rec = get_record(con, args.record)
        if rec is None:
            print(f"Không tìm thấy record: {args.record}", file=sys.stderr)
            return 1
        print_answer(rec, full_quote=args.full_quote)
        return 0

    if not args.query:
        print("Cần câu hỏi hoặc --record.", file=sys.stderr)
        return 1

    query_ascii = normalize_text(args.query)
    vehicle = args.vehicle or detect_vehicle(query_ascii)
    aliases = find_aliases(con, query_ascii)

    if not aliases:
        print("## Chưa đủ chắc chắn để trả lời")
        print()
        print("Catalog chưa khớp chính xác câu hỏi này. Các bản ghi gần nhất:")
        print()
        results = fts_search(con, args.query, vehicle, 5)
        print_search_results(results)
        print()
        print("Bạn nói rõ hơn hành vi và loại xe (xe máy/ô tô) để tra đúng khung.")
        return 0

    alias = aliases[0]

    if vehicle is None:
        by_vehicle = {
            key: alias_record_ids(con, alias["id"], key)
            for key in ("xe_may", "o_to")
        }
        available = {key: items for key, items in by_vehicle.items() if items}
        if len(available) > 1:
            print(f"## {alias['canonical']}")
            print()
            print("Cần biết bạn đi xe máy hay ô tô để chọn đúng khung phạt:")
            for key, items in available.items():
                low = min(item["fine_min"] or 0 for item in items)
                high = max(item["fine_max"] or 0 for item in items)
                detail = f"{len(items)} khung" if len(items) > 1 else "1 khung"
                print(
                    f"- {VEHICLE_LABELS[key]}: {format_range(low, high)} "
                    f"({detail})"
                )
            print()
            print("Bạn đi xe máy hay ô tô?")
            return 0
        if available:
            vehicle = next(iter(available))
            records = available[vehicle]
        else:
            records = []
    else:
        records = alias_record_ids(con, alias["id"], vehicle)

    if not records and vehicle:
        other = "xe_may" if vehicle == "o_to" else "o_to"
        records = alias_record_ids(con, alias["id"], other)
        if records:
            print(
                f"Lưu ý: dữ liệu hiện chỉ có khung phạt cho "
                f"{VEHICLE_LABELS[other].lower()}, không có khung riêng cho "
                f"{VEHICLE_LABELS[vehicle].lower()}."
            )
            print()
            if len(records) == 1:
                print_answer(
                    get_record(con, records[0]["record_id"]),
                    args.full_quote,
                    alias["canonical"],
                )
            else:
                explain_clarification(alias, records)
            return 0

    if not records:
        print(f"## {alias['canonical']}")
        print()
        print("Alias này chưa được gắn với bản ghi nào.")
        return 0

    if len(records) > 1:
        explain_clarification(alias, records)
        return 0

    record = get_record(con, records[0]["record_id"])
    if record is None:
        print(f"Không tìm thấy record: {records[0]['record_id']}", file=sys.stderr)
        return 1
    print_answer(record, args.full_quote, alias["canonical"])
    return 0


def cmd_stats(con: sqlite3.Connection, _args: argparse.Namespace) -> int:
    meta = {row["key"]: row["value"] for row in con.execute("SELECT * FROM catalog_meta")}
    print("Catalog:", meta.get("source_violations"))
    print("Hợp nhất đến:", meta.get("consolidated_as_of"))
    print("Build lúc:", meta.get("built_at"))
    print()
    for key in ("violations", "penalty_rules", "alias_groups", "alias_phrases"):
        print(f"{key}: {meta.get(key)}")
    if "procedures" in meta:
        for key in ("procedures", "procedure_sources", "procedure_citations"):
            print(f"{key}: {meta[key]}")
    print()
    print("Theo Điều:")
    for row in con.execute(
        "SELECT article, COUNT(*) AS n FROM violations GROUP BY article ORDER BY article"
    ):
        print(f"  Điều {row['article']}: {row['n']}")
    print("Theo loại xe:")
    for row in con.execute(
        "SELECT vehicle_type, COUNT(*) AS n FROM violations GROUP BY vehicle_type ORDER BY vehicle_type"
    ):
        print(f"  {row['vehicle_type']}: {row['n']}")
    print("Theo nhóm hành vi:")
    for row in con.execute(
        "SELECT behavior_group, COUNT(*) AS n FROM violations GROUP BY behavior_group ORDER BY behavior_group"
    ):
        print(f"  {row['behavior_group']}: {row['n']}")
    counts = con.execute(
        """
        SELECT
          SUM(record_kind = 'fine') AS fine,
          SUM(record_kind = 'warning') AS warning,
          SUM(record_kind = 'additional_only') AS additional_only,
          SUM(license_points > 0) AS with_points,
          SUM(json_array_length(additional_penalties) > 0) AS with_penalties,
          SUM(json_array_length(remedial_measures) > 0) AS with_remedial
        FROM violations
        """
    ).fetchone()
    print("Phân loại:")
    for key in counts.keys():
        print(f"  {key}: {counts[key]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    sub = parser.add_subparsers(dest="command", required=True)

    search = sub.add_parser("search", help="tìm bản ghi theo câu hỏi")
    search.add_argument("query")
    search.add_argument("--vehicle", choices=("xe_may", "o_to"))
    search.add_argument("--limit", type=int, default=10)
    search.add_argument("--show-score", action="store_true")
    search.set_defaults(func=cmd_search)

    procedure = sub.add_parser("procedure", help="tìm đoạn thủ tục và trích dẫn nguồn")
    procedure.add_argument("query")
    procedure.add_argument("--limit", type=int, default=3)
    procedure.set_defaults(func=cmd_procedure)

    answer = sub.add_parser("answer", help="soạn câu trả lời từ alias/record")
    answer.add_argument("query", nargs="?")
    answer.add_argument("--vehicle", choices=("xe_may", "o_to"))
    answer.add_argument("--record")
    answer.add_argument("--full-quote", action="store_true")
    answer.set_defaults(func=cmd_answer)

    record = sub.add_parser("record", help="xem một bản ghi đầy đủ")
    record.add_argument("record_id")
    record.add_argument("--json", action="store_true")
    record.set_defaults(func=cmd_record)

    stats = sub.add_parser("stats", help="thống kê database")
    stats.set_defaults(func=cmd_stats)

    args = parser.parse_args()
    con = open_db(args.db)
    try:
        return args.func(con, args)
    finally:
        con.close()


if __name__ == "__main__":
    sys.exit(main())
