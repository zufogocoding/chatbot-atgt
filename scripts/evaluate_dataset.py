#!/usr/bin/env python3
"""Validate golden labels and score the current lookup and procedure retrieval baselines."""
from __future__ import annotations

import argparse
from collections import Counter
from contextlib import closing, redirect_stdout
from hashlib import sha256
from io import StringIO
import json
from math import ceil
import re
from pathlib import Path
import sqlite3
from time import perf_counter
from unittest.mock import patch
from urllib.error import URLError
from urllib.request import Request, urlopen

from audit_fines import audit
from catalog_common import format_fine, format_range, load_jsonl, normalize_text
import query_catalog as lookup

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
STOPWORDS = set(
    """va la cua cho trong khi thi tu den ve ra vao mot cac nhung neu bi duoc
    khong nguoi ta toi ban co the se da dang nay do boi vi voi tren duoi tai
    theo hoac ma nhu de phai roi con cung mot cach""".split()
)


def content_tokens(text: str) -> set[str]:
    return {
        word for word in re.findall(r"[a-z0-9]+", normalize_text(text))
        if len(word) > 1 and word not in STOPWORDS
    }


def numeric_tokens(text: str) -> set[str]:
    return set(re.findall(r"\d+(?:[.,]\d+)?", normalize_text(text)))


def keypoint_coverage(expected: str, answer: str) -> float:
    expected_tokens = content_tokens(expected)
    if not expected_tokens:
        return 1.0
    return len(expected_tokens & content_tokens(answer)) / len(expected_tokens)


CATEGORY_LIMITS = {
    "xe_may": (60, 80),
    "o_to": (60, 80),
    "thu_tuc": (40, 50),
    "thieu_ngoai_pham_vi": (20, 30),
    "teencode_khong_dau": (20, 30),
}


def unique_index(rows: list[dict]) -> dict:
    indexed = {row["id"]: row for row in rows}
    if len(indexed) != len(rows):
        raise ValueError("Duplicate IDs in dataset")
    return indexed


def check_dataset(cases: list[dict], procedures: list[dict], records: dict, snapshot: str) -> None:
    unique_index(cases)
    corpus = unique_index(procedures)
    sources = unique_index(json.loads((DATA / "procedures/sources.json").read_text(encoding="utf-8")))
    reconciled = unique_index(audit())
    for source in sources.values():
        if not source["url"].startswith("https://"):
            raise ValueError(f"{source['id']}: missing HTTPS source")
        if "local_path" in source:
            local = (ROOT / source["local_path"]).read_bytes()
            if sha256(local).hexdigest() != source["sha256"]:
                raise ValueError(f"{source['id']}: source PDF checksum differs")
    for chunk in corpus.values():
        if not all(chunk.get(key) for key in ("title", "text", "keywords", "sources")):
            raise ValueError(f"{chunk['id']}: incomplete procedure chunk")
        if chunk["as_of"] != snapshot or chunk["topic"] not in {"nop_phat", "khieu_nai"}:
            raise ValueError(f"{chunk['id']}: invalid topic or snapshot")
        for ref in chunk["sources"]:
            if ref["source_id"] not in sources or not ref["locator"]:
                raise ValueError(f"{chunk['id']}: unknown source or missing locator")

    counts = Counter(case["category"] for case in cases)
    if set(counts) != set(CATEGORY_LIMITS):
        raise ValueError("Golden categories differ from project brief")
    if not 200 <= len(cases) <= 300:
        raise ValueError("Golden set must contain 200–300 cases")
    for key, (low, high) in CATEGORY_LIMITS.items():
        if not low <= counts[key] <= high:
            raise ValueError(f"{key}: {counts[key]} outside [{low}, {high}]")
    questions = [normalize_text(case["question"]) for case in cases]
    if not all(questions) or len(questions) != len(set(questions)):
        raise ValueError("Golden questions are empty or duplicate after normalization")

    for case in cases:
        rid = case["expected_violation_id"]
        kind = case["expected_answer_type"]
        if kind == "penalty":
            rec, source = records[rid], reconciled[rid]
            org = case["expected_fine_subject"] == "to_chuc"
            if case["expected_fine_subject"] not in {"ca_nhan", "to_chuc"}:
                raise ValueError(f"{case['id']}: unknown fine subject")
            prefix = "expected_fine_org" if org else "expected_fine"
            expected = {side: source[f"{prefix}_{side}"] for side in ("min", "max")}
            expected_unit = case.get("expected_fine_unit")
            cap_field = "expected_fine_org_cap" if org else "expected_fine_cap"
            expected_cap = case.get(cap_field)
            unit_ok = expected_unit == source["fine_unit"]
            cap_ok = expected_cap == source[cap_field]
            vehicle = case["expected_vehicle_type"]
            if (source["audit_result"] != "match" or case["expected_fine"] != expected
                    or not unit_ok or not cap_ok
                    or case["expected_record_kind"] != rec["record_kind"]
                    or case["expected_legal_basis"] != rec["legal_basis"]
                    or rec["vehicle_type"] not in {vehicle, "both"}
                    or vehicle not in {"xe_may", "o_to"}
                    or (org and expected["min"] is None)):
                raise ValueError(f"{case['id']}: penalty label disagrees with audit or catalog")
        elif kind == "procedure":
            if not case["expected_key_points"] or not case["expected_procedure_ids"] or rid:
                raise ValueError(f"{case['id']}: incomplete procedure label")
            citations = [
                {"source_id": ref["source_id"], "locator": ref["locator"]}
                for chunk_id in case["expected_procedure_ids"] for ref in corpus[chunk_id]["sources"]
            ]
            if case["expected_legal_basis"] != citations:
                raise ValueError(f"{case['id']}: procedure citations differ from source chunks")
        elif kind not in {"clarify", "refuse"} or not case.get("expected_reason") or rid:
            raise ValueError(f"{case['id']}: invalid guardrail label")


def penalty_top5(con: sqlite3.Connection, question: str) -> list[str]:
    normalized = normalize_text(question)
    vehicle = lookup.detect_vehicle(normalized)
    for alias in lookup.find_aliases(con, normalized):
        items = lookup.alias_record_ids(con, alias["id"], vehicle)
        if items:
            return list(dict.fromkeys(item["record_id"] for item in items))[:5]
    return [rec["id"] for rec in lookup.fts_search(con, question, vehicle, 5)]


def cli_answer(con: sqlite3.Connection, question: str) -> tuple[str, dict | None, str]:
    args = argparse.Namespace(query=question, record=None, vehicle=None, full_quote=False)
    output = StringIO()
    with redirect_stdout(output), patch.object(lookup, "print_answer", wraps=lookup.print_answer) as render:
        lookup.cmd_answer(con, args)
    answer = output.getvalue()
    if render.called:
        return "penalty", render.call_args.args[0], answer
    if "Cần " in answer or "Bạn nói rõ hơn" in answer:
        return "clarify", None, answer
    return "refuse", None, answer


def score(con: sqlite3.Connection, cases: list[dict], details: bool) -> dict:
    stats = Counter()
    for case in cases:
        kind = case["expected_answer_type"]
        question = case["question"]
        stats[f"{kind}_cases"] += 1
        if kind == "procedure":
            candidates = [row["id"] for row in lookup.search_procedures(con, question, 5)]
            hit = any(rid in candidates for rid in case["expected_procedure_ids"])
            stats["procedure_recall_at_5"] += hit
            if details and not hit:
                print(f"{case['id']} {question} → {candidates}")
            continue

        actual_type, rec, answer = cli_answer(con, question)
        if kind != "penalty":
            stats[f"{kind}_correct"] += actual_type == kind
            if details and actual_type != kind:
                print(f"{case['id']} {question} → {actual_type}, expected {kind}")
            continue

        expected_id = case["expected_violation_id"]
        stats["penalty_recall_at_5"] += expected_id in penalty_top5(con, question)
        stats["penalty_answered"] += rec is not None
        stats["penalty_record_exact"] += rec is not None and rec["id"] == expected_id
        basis = case["expected_legal_basis"]
        stats["penalty_citation_exact"] += bool(
            rec and rec["document"] == basis["document"] and rec["legal_path"] == basis["path"]
        )
        if rec:
            fine = case["expected_fine"]
            org = case["expected_fine_subject"] == "to_chuc"
            label = "Mức phạt (tổ chức)" if org else "Mức phạt"
            if fine["min"] is None:
                fine_line = "- Mức phạt tiền: Không có"
            elif fine["min"] == 0:
                fine_line = "- Mức phạt: Phạt cảnh cáo"
            else:
                cap = case.get("expected_fine_org_cap" if org else "expected_fine_cap")
                rendered = format_fine(
                    fine["min"], fine["max"], case.get("expected_fine_unit"), cap,
                )
                if label == "Mức phạt" and rec.get("fine_org_min") is not None:
                    label = "Mức phạt (cá nhân)"
                fine_line = f"- {label}: {rendered}"
            stats["penalty_fine_exact"] += fine_line in answer.splitlines()
        if details and (not rec or rec["id"] != expected_id):
            print(f"{case['id']} {question} → {rec['id'] if rec else actual_type}, expected {expected_id}")
    return dict(stats)


def evaluate_api(url: str, cases: list[dict], failures: bool) -> None:
    manifest = unique_index(json.loads((DATA / "procedures/sources.json").read_text(encoding="utf-8")))
    stats = Counter()
    latencies = []
    for case in cases:
        question = case["question"]
        payload = json.dumps({"question": question}, ensure_ascii=False).encode("utf-8")
        request = Request(url, data=payload, headers={"Content-Type": "application/json; charset=utf-8"})
        start = perf_counter()
        with urlopen(request, timeout=10) as response:
            answer = json.load(response)
        latencies.append((perf_counter() - start) * 1000)
        kind = case["expected_answer_type"]
        stats[f"{kind}_cases"] += 1
        matches = answer["answer_type"] == kind
        if answer["answer_type"] in {"penalty", "procedure"} and not answer["sources"]:
            stats["without_sources"] += 1
        if kind == "penalty":
            penalty = answer["penalty"] or {}
            org = case["expected_fine_subject"] == "to_chuc"
            fine_key = "organization_fine" if org else "fine"
            actual_fine = penalty.get(fine_key) or {}
            expected_fine = case["expected_fine"]
            expected_cap = case.get("expected_fine_org_cap" if org else "expected_fine_cap")
            stats["fine_exact"] += matches and (
                actual_fine.get("min"), actual_fine.get("max"),
                actual_fine.get("unit"), actual_fine.get("cap"),
            ) == (
                expected_fine["min"], expected_fine["max"],
                case.get("expected_fine_unit"), expected_cap,
            )
            citation_matches = (
                matches and bool(answer["sources"])
                and penalty.get("legal_path") == case["expected_legal_basis"]["path"]
            )
            stats["citation_exact"] += citation_matches
            matches = citation_matches and penalty.get("record_id") == case["expected_violation_id"]
        elif kind == "procedure":
            expected = {(manifest[ref["source_id"]]["number"], ref["locator"], manifest[ref["source_id"]]["url"])
                        for ref in case["expected_legal_basis"]}
            actual = {(source["document"], source["locator"], source["url"]) for source in answer["sources"]}
            matches = matches and expected <= actual and set(case["expected_procedure_ids"]) <= set(answer["procedure_ids"])
            key_points = case.get("expected_key_points") or ""
            coverage = keypoint_coverage(key_points, answer["answer"])
            stats["procedure_keypoint_sum"] += coverage
            stats["procedure_keypoint_cases"] += 1
            stats["procedure_low_coverage"] += coverage < 0.6
            stats["procedure_missing_number"] += bool(
                numeric_tokens(key_points) - numeric_tokens(answer["answer"])
            )
            markers = [int(marker) for marker in re.findall(r"\[(\d+)\]", answer["answer"])]
            stats["procedure_citation_integrity"] += bool(
                markers and set(markers) == set(range(1, len(answer["sources"]) + 1))
            )
        stats[f"{kind}_correct"] += matches
        if failures and not matches:
            print(f"{case['id']} {question} → {answer['answer_type']}: {answer['reason'] or answer['procedure_ids']}")

    for label, key, denominator in [
        ("Đúng bản ghi mức phạt", "penalty_correct", "penalty_cases"),
        ("Đúng cả min/max", "fine_exact", "penalty_cases"),
        ("Đúng căn cứ mức phạt", "citation_exact", "penalty_cases"),
        ("Đúng đoạn và căn cứ thủ tục", "procedure_correct", "procedure_cases"),
        ("Hỏi lại", "clarify_correct", "clarify_cases"),
        ("Từ chối", "refuse_correct", "refuse_cases"),
    ]:
        hits, total = stats[key], stats[denominator]
        print(f"{label}: {hits}/{total} ({hits / total:.1%})")
    coverage_cases = stats["procedure_keypoint_cases"]
    coverage = stats["procedure_keypoint_sum"] / coverage_cases if coverage_cases else 0
    print(f"Thủ tục — số liệu khớp: {coverage_cases - stats['procedure_missing_number']}/{coverage_cases}")
    print(f"Thủ tục — độ phủ từ khóa trung bình: {coverage:.1%}")
    print(f"Thủ tục — ca dưới 60% từ khóa: {stats['procedure_low_coverage']}/{coverage_cases}")
    print(f"Thủ tục — trích dẫn hợp lệ: {stats['procedure_citation_integrity']}/{coverage_cases}")
    print(f"Câu trả lời thiếu nguồn: {stats['without_sources']}")
    print(f"Độ trễ HTTP p95: {sorted(latencies)[ceil(0.95 * len(latencies)) - 1]:.1f} ms")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, default=lookup.DEFAULT_DB)
    parser.add_argument(
        "--violations",
        type=Path,
        default=DATA / "catalog/consolidated/violations.jsonl",
        help="violation JSONL the SQLite database was built from",
    )
    parser.add_argument("--failures", action="store_true", help="show mismatched cases")
    parser.add_argument("--api-url", help="score a running /chat endpoint instead of the CLI baseline")
    args = parser.parse_args()
    cases = load_jsonl(DATA / "eval/golden.jsonl")
    procedures = load_jsonl(DATA / "procedures/procedures.jsonl")
    records = unique_index(load_jsonl(DATA / "catalog/consolidated/violations.jsonl"))
    snapshot, = {r["version"]["consolidated_as_of"] for r in records.values()}
    check_dataset(cases, procedures, records, snapshot)
    print(f"Dataset checks passed: {len(records)} records, {len(procedures)} chunks, {len(cases)} cases")
    if args.api_url:
        try:
            evaluate_api(args.api_url, cases, args.failures)
        except URLError as error:
            raise SystemExit(f"Không gọi được API tại {args.api_url}: {error}") from error
        return 0
    with closing(lookup.open_db(args.db)) as con:
        db_records = unique_index(load_jsonl(args.violations))
        stored = {row[0]: json.loads(row[1]) for row in con.execute("SELECT id, raw_json FROM violations")}
        if stored != db_records or not con.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'procedures_fts'"
        ).fetchone():
            raise SystemExit("SQLite does not match catalog. Run scripts/build_db.py.")
        stored_procedures = [
            dict(row) | {"keywords": json.loads(row["keywords"])}
            for row in con.execute("SELECT * FROM procedures ORDER BY id")
        ]
        expected = [
            {key: value for key, value in item.items() if key != "sources"}
            for item in sorted(procedures, key=lambda item: item["id"])
        ]
        if stored_procedures != expected:
            raise SystemExit("SQLite does not match procedure data. Run scripts/build_db.py.")
        results = score(con, cases, args.failures)
    for label, key, denominator in [
        ("Tra cứu có cấu trúc — recall@5", "penalty_recall_at_5", "penalty_cases"),
        ("Tra cứu có cấu trúc — trả lời được", "penalty_answered", "penalty_cases"),
        ("Tra cứu có cấu trúc — đúng bản ghi", "penalty_record_exact", "penalty_cases"),
        ("Tra cứu có cấu trúc — đúng cả min/max", "penalty_fine_exact", "penalty_cases"),
        ("Tra cứu có cấu trúc — đúng căn cứ", "penalty_citation_exact", "penalty_cases"),
        ("Tra cứu có cấu trúc — hỏi lại", "clarify_correct", "clarify_cases"),
        ("Tra cứu có cấu trúc — từ chối", "refuse_correct", "refuse_cases"),
        ("Thủ tục — BM25 recall@5", "procedure_recall_at_5", "procedure_cases"),
    ]:
        hits, total = results.get(key, 0), results[denominator]
        print(f"{label}: {hits}/{total} ({hits / total:.1%})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
