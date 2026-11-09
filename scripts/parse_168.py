#!/usr/bin/env python3
"""Parse the consolidated text of Nghị định 168/2024/NĐ-CP.

Input : data/parsed/168-2024-nd-cp-full.txt
Output: data/parsed/168-provisions.jsonl
        data/parsed/168-articles.json

The parser is deliberately structure-based, not LLM-based: legal documents
follow a strict Điều / khoản / điểm hierarchy, and we want reproducible output.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data/parsed/168-2024-nd-cp-full.txt"
OUT_PROVISIONS = ROOT / "data/parsed/168-provisions.jsonl"
OUT_ARTICLES = ROOT / "data/parsed/168-articles.json"

ARTICLE_RE = re.compile(r"^\s*Điều\s+(\d+)\s*\.\s*(.*)$")
CLAUSE_RE = re.compile(r"^\s*(\d{1,2})\s*\.\s+(.*)$")
POINT_RE = re.compile(r"^\s*([a-zđ])\s*\)\s*(.*)$")
HEADER_RE = re.compile(r"CÔNG BÁO/Số", re.IGNORECASE)
PAGE_ONLY_RE = re.compile(r"^\s*\d{1,4}\s*$")


def clean_lines(text: str) -> list[str]:
    lines: list[str] = []
    started = False
    for raw in text.splitlines():
        line = raw.replace("\u00a0", " ").rstrip()
        if not started:
            if line.strip().startswith("Chương I"):
                started = True
            else:
                continue
        if HEADER_RE.search(line):
            continue
        if PAGE_ONLY_RE.match(line):
            continue
        if line.strip().startswith("Chương ") or line.strip().startswith("Mục "):
            # keep chapter/section markers only as separators
            lines.append(line.strip())
            continue
        if not line.strip():
            continue
        lines.append(line)
    return lines


def flush(block: list[str]) -> str:
    return " ".join(x.strip() for x in block).strip()


def parse(lines: list[str]) -> tuple[list[dict], list[dict]]:
    provisions: list[dict] = []
    articles: list[dict] = []

    article_no: int | None = None
    article_title_parts: list[str] = []
    clause_no: int | None = None
    point: str | None = None
    block: list[str] = []
    current_article: dict | None = None

    def add_provision() -> None:
        nonlocal block
        body = flush(block)
        if article_no is None or not body:
            block = []
            return
        provisions.append(
            {
                "document": "168/2024/NĐ-CP",
                "article": article_no,
                "article_title": " ".join(article_title_parts).strip(),
                "clause": clause_no,
                "point": point,
                "path": f"{article_no}.{clause_no}" + (f".{point}" if point else ""),
                "text": body,
            }
        )
        block = []

    for line in lines:
        m_article = ARTICLE_RE.match(line)
        if m_article:
            add_provision()
            article_no = int(m_article.group(1))
            article_title_parts = [m_article.group(2).strip()]
            clause_no = None
            point = None
            current_article = {
                "article": article_no,
                "title": "",
                "clauses": 0,
                "points": 0,
            }
            articles.append(current_article)
            continue

        if article_no is None:
            continue

        m_clause = CLAUSE_RE.match(line)
        if m_clause:
            add_provision()
            clause_no = int(m_clause.group(1))
            point = None
            block = [m_clause.group(2).strip()]
            if current_article is not None:
                current_article["clauses"] += 1
            continue

        m_point = POINT_RE.match(line)
        if m_point:
            add_provision()
            point = m_point.group(1)
            block = [m_point.group(2).strip()]
            if current_article is not None:
                current_article["points"] += 1
            continue

        # continuation line
        if clause_no is None:
            article_title_parts.append(line.strip())
        else:
            block.append(line.strip())

    add_provision()

    # Fill article titles and drop incomplete articles
    title_by_article = {}
    for p in provisions:
        title_by_article.setdefault(p["article"], p["article_title"])
    for a in articles:
        a["title"] = title_by_article.get(a["article"], a["title"])
    return provisions, articles


def main() -> None:
    text = INPUT.read_text(encoding="utf-8")
    lines = clean_lines(text)
    provisions, articles = parse(lines)

    OUT_PROVISIONS.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PROVISIONS.open("w", encoding="utf-8") as f:
        for p in provisions:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    OUT_ARTICLES.write_text(json.dumps(articles, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"provisions: {len(provisions)}")
    print(f"articles: {len(articles)}")
    print(f"output: {OUT_PROVISIONS}")
    print(f"output: {OUT_ARTICLES}")


if __name__ == "__main__":
    main()
