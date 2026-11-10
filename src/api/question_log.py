"""Persistent question logs kept separately from the traffic catalog."""
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path
import re
import sqlite3

from .schemas import ChatResponse

IDENTIFIERS = re.compile(
    r"\b[\w.+%+-]+@[\w.-]+\.\w+\b"  # email
    r"|\b\d{2}[ -]?[A-Z][A-Z0-9]?[ -]?\d{3}[. -]?\d{2}\b"  # common VN plates
    r"|(?<!\w)\+?(?:\d[ .-]?){8,}\d(?!\w)",  # phone and ID numbers
    re.IGNORECASE,
)


def append_question_log(path: Path, question: str, response: ChatResponse) -> None:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    question = IDENTIFIERS.sub("[đã ẩn]", question)
    record_id = response.penalty.record_id if response.penalty is not None else None

    path.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(path, timeout=1.0)) as connection, connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS question_log (
                question TEXT NOT NULL,
                answer_type TEXT NOT NULL,
                record_id TEXT,
                reason TEXT,
                timestamp TEXT NOT NULL
            )
        """)
        connection.execute(
            "INSERT INTO question_log (question, answer_type, record_id, reason, timestamp) VALUES (?, ?, ?, ?, ?)",
            (question, response.answer_type, record_id, response.reason, timestamp),
        )
