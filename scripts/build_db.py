#!/usr/bin/env python3
"""Build the SQLite catalog used by the chatbot and lookup tools.

The JSONL files remain the source of truth. This script is a deterministic
projection: delete the database, rebuild it, verify counts and foreign keys.

Input : data/catalog/consolidated/violations.jsonl
        data/catalog/consolidated/penalty-rules.jsonl
        data/catalog/aliases.json
        data/procedures/procedures.jsonl
        data/procedures/sources.json
Output: data/build/catalog.db

Run: python3 scripts/build_db.py
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sqlite3
import sys
import tempfile
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from catalog_common import load_jsonl, normalize_text  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
VIOLATIONS = ROOT / "data/catalog/consolidated/violations.jsonl"
RULES = ROOT / "data/catalog/consolidated/penalty-rules.jsonl"
ALIASES = ROOT / "data/catalog/aliases.json"
PROCEDURES = ROOT / "data/procedures/procedures.jsonl"
PROCEDURE_SOURCES = ROOT / "data/procedures/sources.json"
DEFAULT_OUT = ROOT / "data/build/catalog.db"


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE catalog_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE violations (
    id                    TEXT PRIMARY KEY,
    document              TEXT NOT NULL,
    document_title        TEXT,
    article_title         TEXT,
    article               INTEGER NOT NULL,
    clause                TEXT NOT NULL,
    point                 TEXT,
    legal_path            TEXT NOT NULL,
    vehicle_type          TEXT NOT NULL,
    subject               TEXT NOT NULL DEFAULT 'nguoi_dieu_khien',
    behavior_group        TEXT NOT NULL,
    behavior_text         TEXT NOT NULL,
    behavior_ascii        TEXT NOT NULL,
    clause_text           TEXT,
    clause_ascii          TEXT NOT NULL,
    fine_min              INTEGER,
    fine_max              INTEGER,
    fine_org_min          INTEGER,
    fine_org_max          INTEGER,
    fine_text             TEXT,
    record_kind           TEXT NOT NULL,
    license_points        INTEGER NOT NULL DEFAULT 0,
    license_points_condition TEXT,
    additional_penalties  TEXT NOT NULL DEFAULT '[]',
    remedial_measures     TEXT NOT NULL DEFAULT '[]',
    penalty_rule_ids      TEXT NOT NULL DEFAULT '[]',
    source_url            TEXT,
    source_quote          TEXT,
    verification_status   TEXT NOT NULL,
    verified_by           TEXT,
    verified_at           TEXT,
    effective_from        TEXT,
    effective_to          TEXT,
    amended_by            TEXT NOT NULL DEFAULT '[]',
    last_amended          TEXT,
    consolidated_as_of    TEXT,
    raw_json              TEXT NOT NULL
);

CREATE INDEX idx_violations_article ON violations(article, clause, point);
CREATE INDEX idx_violations_vehicle ON violations(vehicle_type);
CREATE INDEX idx_violations_group ON violations(behavior_group);

CREATE VIRTUAL TABLE violations_fts USING fts5(
    id UNINDEXED,
    behavior_ascii,
    clause_ascii,
    tokenize = 'unicode61'
);

CREATE TABLE penalty_rules (
    id          TEXT PRIMARY KEY,
    document    TEXT NOT NULL,
    article     INTEGER NOT NULL,
    clause      TEXT NOT NULL,
    point       TEXT,
    text        TEXT NOT NULL,
    refs        TEXT NOT NULL,
    penalty     TEXT NOT NULL,
    amended_by  TEXT,
    raw_json    TEXT NOT NULL
);

CREATE TABLE alias_groups (
    id                 TEXT PRIMARY KEY,
    canonical          TEXT NOT NULL,
    requires_qualifier INTEGER NOT NULL DEFAULT 0,
    notes              TEXT
);

CREATE TABLE alias_phrases (
    alias_id      TEXT NOT NULL REFERENCES alias_groups(id) ON DELETE CASCADE,
    phrase        TEXT NOT NULL,
    phrase_ascii  TEXT NOT NULL,
    PRIMARY KEY (alias_id, phrase_ascii)
);

CREATE INDEX idx_alias_phrases_ascii ON alias_phrases(phrase_ascii);

CREATE TABLE alias_records (
    alias_id     TEXT NOT NULL REFERENCES alias_groups(id) ON DELETE CASCADE,
    vehicle_type TEXT NOT NULL,
    record_id    TEXT NOT NULL REFERENCES violations(id),
    qualifier    TEXT,
    PRIMARY KEY (alias_id, vehicle_type, record_id)
);

CREATE INDEX idx_alias_records_record ON alias_records(record_id);

CREATE TABLE procedures (
    id       TEXT PRIMARY KEY,
    topic    TEXT NOT NULL CHECK (topic IN ('nop_phat', 'khieu_nai')),
    title    TEXT NOT NULL,
    text     TEXT NOT NULL,
    keywords TEXT NOT NULL,
    as_of    TEXT NOT NULL
);

CREATE INDEX idx_procedures_topic ON procedures(topic);

CREATE TABLE procedure_sources (
    id           TEXT PRIMARY KEY,
    number       TEXT NOT NULL,
    title        TEXT NOT NULL,
    publisher    TEXT NOT NULL,
    issued_on    TEXT,
    url          TEXT NOT NULL,
    checked_on   TEXT NOT NULL,
    local_path   TEXT,
    sha256       TEXT,
    related_urls TEXT NOT NULL
);

CREATE TABLE procedure_citations (
    procedure_id TEXT NOT NULL REFERENCES procedures(id) ON DELETE CASCADE,
    position     INTEGER NOT NULL,
    source_id    TEXT NOT NULL REFERENCES procedure_sources(id),
    locator      TEXT NOT NULL CHECK (length(trim(locator)) > 0),
    pages        TEXT,
    PRIMARY KEY (procedure_id, position)
);

CREATE INDEX idx_procedure_citations_source ON procedure_citations(source_id);

CREATE VIRTUAL TABLE procedures_fts USING fts5(
    id UNINDEXED,
    title_ascii,
    keywords_ascii,
    text_ascii,
    tokenize = 'unicode61'
);
"""


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def insert_violations(con: sqlite3.Connection, records: list[dict[str, Any]]) -> None:
    for rec in records:
        basis = rec["legal_basis"]
        version = rec.get("version", {})
        verification = rec.get("verification", {})
        org = rec.get("fine_by_subject", {}).get("to_chuc", {})
        con.execute(
            """
            INSERT INTO violations (
                id, document, document_title, article_title,
                article, clause, point, legal_path,
                vehicle_type, subject, behavior_group,
                behavior_text, behavior_ascii, clause_text, clause_ascii,
                fine_min, fine_max, fine_org_min, fine_org_max, fine_text,
                record_kind, license_points, license_points_condition,
                additional_penalties, remedial_measures, penalty_rule_ids,
                source_url, source_quote,
                verification_status, verified_by, verified_at,
                effective_from, effective_to, amended_by, last_amended,
                consolidated_as_of, raw_json
            ) VALUES (
                ?, ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?,
                ?, ?, ?,
                ?, ?,
                ?, ?, ?,
                ?, ?, ?, ?,
                ?, ?
            )
            """,
            (
                rec["id"],
                rec["document"],
                rec.get("document_title"),
                rec.get("article_title"),
                basis["article"],
                str(basis["clause"]),
                basis.get("point"),
                basis["path"],
                rec["vehicle_type"],
                rec.get("subject", "nguoi_dieu_khien"),
                rec["behavior_group"],
                rec["behavior_text"],
                normalize_text(rec["behavior_text"]),
                rec.get("clause_text", ""),
                normalize_text(rec.get("clause_text", "")),
                rec.get("fine_min"),
                rec.get("fine_max"),
                org.get("min"),
                org.get("max"),
                rec.get("fine_text"),
                rec["record_kind"],
                rec.get("license_points", 0),
                rec.get("license_points_condition"),
                json_text(rec.get("additional_penalties", [])),
                json_text(rec.get("remedial_measures", [])),
                json_text(rec.get("penalty_rule_ids", [])),
                rec.get("source_url"),
                rec.get("source_quote"),
                verification.get("status", "draft"),
                verification.get("verified_by"),
                verification.get("verified_at"),
                version.get("effective_from"),
                version.get("effective_to"),
                json_text(version.get("amended_by", [])),
                version.get("last_amended"),
                version.get("consolidated_as_of"),
                json_text(rec),
            ),
        )
    con.execute(
        "INSERT INTO violations_fts (id, behavior_ascii, clause_ascii) "
        "SELECT id, behavior_ascii, clause_ascii FROM violations"
    )


def insert_rules(con: sqlite3.Connection, rules: list[dict[str, Any]]) -> None:
    for rule in rules:
        con.execute(
            """
            INSERT INTO penalty_rules (
                id, document, article, clause, point, text, refs, penalty,
                amended_by, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                rule["id"],
                rule["document"],
                rule["article"],
                str(rule["clause"]),
                rule.get("point"),
                rule["text"],
                json_text(rule.get("refs", [])),
                json_text(rule["penalty"]),
                rule.get("amended_by"),
                json_text(rule),
            ),
        )


def insert_aliases(con: sqlite3.Connection, aliases: dict[str, Any]) -> tuple[int, int]:
    phrase_count = 0
    for entry in aliases.get("aliases", []):
        con.execute(
            "INSERT INTO alias_groups (id, canonical, requires_qualifier, notes) "
            "VALUES (?, ?, ?, ?)",
            (
                entry["id"],
                entry["canonical"],
                1 if entry.get("requires_qualifier") else 0,
                entry.get("notes"),
            ),
        )
        for phrase in entry.get("citizen_phrases", []):
            phrase_ascii = normalize_text(phrase)
            if not phrase_ascii:
                raise SystemExit(f"alias {entry['id']}: empty phrase after normalization")
            # Accented and unaccented variants collapse to the same key.
            cursor = con.execute(
                "INSERT OR IGNORE INTO alias_phrases (alias_id, phrase, phrase_ascii) "
                "VALUES (?, ?, ?)",
                (entry["id"], phrase, phrase_ascii),
            )
            phrase_count += cursor.rowcount
        for vehicle, items in entry.get("records", {}).items():
            for item in items:
                con.execute(
                    "INSERT OR IGNORE INTO alias_records "
                    "(alias_id, vehicle_type, record_id, qualifier) "
                    "VALUES (?, ?, ?, ?)",
                    (entry["id"], vehicle, item["record_id"], item.get("qualifier")),
                )
    return len(aliases.get("aliases", [])), phrase_count


def insert_procedures(con: sqlite3.Connection, procedures: list[dict], sources: list[dict]) -> None:
    con.executemany(
        "INSERT INTO procedures (id, topic, title, text, keywords, as_of) VALUES (?, ?, ?, ?, ?, ?)",
        [(p["id"], p["topic"], p["title"], p["text"], json_text(p["keywords"]), p["as_of"])
         for p in procedures],
    )
    con.executemany(
        """
        INSERT INTO procedure_sources (id, number, title, publisher, issued_on,
                                       url, checked_on, local_path, sha256, related_urls)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [(s["id"], s["number"], s["title"], s["publisher"], s.get("issued_on"),
          s["url"], s["checked_on"], s.get("local_path"), s.get("sha256"),
          json_text(s.get("related_urls", []))) for s in sources],
    )
    con.executemany(
        """
        INSERT INTO procedure_citations (procedure_id, position, source_id, locator, pages)
        VALUES (?, ?, ?, ?, ?)
        """,
        [(p["id"], position, ref["source_id"], ref["locator"],
          json_text(ref["pages"]) if "pages" in ref else None)
         for p in procedures for position, ref in enumerate(p["sources"])],
    )
    con.executemany(
        "INSERT INTO procedures_fts (id, title_ascii, keywords_ascii, text_ascii) VALUES (?, ?, ?, ?)",
        [(p["id"], normalize_text(p["title"]), normalize_text(" ".join(p["keywords"])),
          normalize_text(p["text"])) for p in procedures],
    )


def verify(con: sqlite3.Connection, expected_counts: dict[str, int]) -> list[str]:
    problems: list[str] = []

    for table, expected in expected_counts.items():
        actual = con.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        if actual != expected:
            problems.append(f"{table} count {actual} != {expected}")

    fk_errors = con.execute("PRAGMA foreign_key_check").fetchall()
    if fk_errors:
        problems.append(f"foreign key errors: {fk_errors}")

    dangling_rules = con.execute(
        """
        SELECT DISTINCT j.value
        FROM violations v, json_each(v.penalty_rule_ids) j
        LEFT JOIN penalty_rules r ON r.id = j.value
        WHERE r.id IS NULL
        """
    ).fetchall()
    if dangling_rules:
        problems.append(f"dangling penalty_rule_ids: {[r[0] for r in dangling_rules]}")

    missing_fts = con.execute(
        """
        SELECT v.id FROM violations v
        LEFT JOIN violations_fts f ON f.id = v.id
        WHERE f.id IS NULL
        """
    ).fetchall()
    if missing_fts:
        problems.append(f"records missing from FTS: {[r[0] for r in missing_fts]}")

    missing_citations = con.execute(
        """
        SELECT p.id FROM procedures p
        WHERE NOT EXISTS (SELECT 1 FROM procedure_citations c WHERE c.procedure_id = p.id)
        """
    ).fetchall()
    if missing_citations:
        problems.append(f"procedures missing citations: {[row[0] for row in missing_citations]}")

    empty_phrases = con.execute(
        "SELECT COUNT(*) FROM alias_phrases WHERE phrase_ascii = ''"
    ).fetchone()[0]
    if empty_phrases:
        problems.append(f"{empty_phrases} empty alias phrases")

    return problems


def build(out: Path) -> int:
    records = load_jsonl(VIOLATIONS)
    rules = load_jsonl(RULES)
    aliases = json.loads(ALIASES.read_text(encoding="utf-8"))
    procedures = load_jsonl(PROCEDURES)
    sources = json.loads(PROCEDURE_SOURCES.read_text(encoding="utf-8"))

    ids = [r["id"] for r in records]
    if len(ids) != len(set(ids)):
        raise SystemExit("duplicate violation ids in consolidated catalog")
    snapshots = {r["version"]["consolidated_as_of"] for r in records}
    if len(snapshots) != 1 or any(p["as_of"] not in snapshots for p in procedures):
        raise SystemExit("violations and procedures must use the same snapshot")
    citation_count = sum(len(p["sources"]) for p in procedures)

    out = out.resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{out.name}.", suffix=".tmp", dir=out.parent)
    os.close(fd)
    tmp = Path(tmp_name)
    try:
        with closing(sqlite3.connect(tmp)) as con:
            con.executescript(SCHEMA)
            insert_violations(con, records)
            insert_rules(con, rules)
            alias_groups, alias_phrases = insert_aliases(con, aliases)
            insert_procedures(con, procedures, sources)

            counts = {
                "violations": len(records),
                "violations_fts": len(records),
                "penalty_rules": len(rules),
                "alias_groups": alias_groups,
                "alias_phrases": alias_phrases,
                "procedures": len(procedures),
                "procedures_fts": len(procedures),
                "procedure_sources": len(sources),
                "procedure_citations": citation_count,
            }
            problems = verify(con, counts)
            if problems:
                for problem in problems:
                    print(f"ERROR {problem}", file=sys.stderr)
                return 1

            meta = {
                **counts,
                "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                "consolidated_as_of": records[0]["version"]["consolidated_as_of"],
                "alias_phrases_raw": sum(
                    len(entry.get("citizen_phrases", [])) for entry in aliases.get("aliases", [])
                ),
            }
            for key, path in {
                "violations": VIOLATIONS, "rules": RULES, "aliases": ALIASES,
                "procedures": PROCEDURES, "procedure_sources": PROCEDURE_SOURCES,
            }.items():
                meta[f"source_{key}"] = str(path.relative_to(ROOT))
                meta[f"source_{key}_sha256"] = sha256(path)
            con.executemany(
                "INSERT INTO catalog_meta (key, value) VALUES (?, ?)",
                [(k, str(v)) for k, v in meta.items()],
            )
            con.commit()
        os.replace(tmp, out)
    finally:
        tmp.unlink(missing_ok=True)

    display_path = out.relative_to(ROOT) if out.is_relative_to(ROOT) else out
    print(f"built {display_path}")
    print(f"  violations: {len(records)}")
    print(f"  penalty rules: {len(rules)}")
    print(f"  alias groups: {alias_groups} ({alias_phrases} phrases)")
    print(f"  procedures: {len(procedures)} ({len(sources)} sources, {citation_count} citations)")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    return build(args.out)


if __name__ == "__main__":
    sys.exit(main())
