"""Read-only catalog access, routing and grounded chat responses."""
from __future__ import annotations

from contextlib import closing
import json
from pathlib import Path
import re
import sqlite3

from scripts.catalog_common import format_money, format_penalty, format_range, legal_path, normalize_text
from scripts.query_catalog import alias_record_ids, find_aliases, fts_search, get_record, search_procedures

from .routing import (
    HISTORICAL, LICENSE, OUTSIDE_REQUEST, OUTSIDE_VEHICLE, PROCEDURE,
    Clarification, direct_path, includes, mentioned_vehicles, normalize_question,
)
from .schemas import (
    ChatRequest, ChatResponse, Choice, Fine, Guidance, HealthResponse, Intent,
    LicensePointTier, Penalty, Source, Vehicle,
)

REQUIRED_TABLES = {
    "catalog_meta", "violations", "violations_fts", "alias_phrases", "alias_groups",
    "alias_records", "procedures", "procedures_fts", "procedure_sources", "procedure_citations",
}
VEHICLE_LABELS = {"xe_may": "xe máy", "o_to": "ô tô"}


def connect_catalog(path: Path) -> sqlite3.Connection:
    con = sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def snapshot(con: sqlite3.Connection) -> str:
    row = con.execute("SELECT value FROM catalog_meta WHERE key = 'consolidated_as_of'").fetchone()
    if not row or not row[0]:
        raise sqlite3.DatabaseError("missing catalog snapshot")
    return row[0]


def health(path: Path) -> HealthResponse:
    with closing(connect_catalog(path)) as con:
        tables = {row[0] for row in con.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        if not REQUIRED_TABLES <= tables:
            raise sqlite3.DatabaseError("incomplete catalog schema")
        return HealthResponse(
            as_of=snapshot(con),
            violations=con.execute("SELECT count(*) FROM violations").fetchone()[0],
            procedures=con.execute("SELECT count(*) FROM procedures").fetchone()[0],
        )


def refuse(as_of: str, reason: str, message: str, intent: Intent = "other") -> ChatResponse:
    return ChatResponse(intent=intent, answer_type="refuse", answer=message, as_of=as_of, reason=reason)


def clarify(as_of: str, info: Clarification, options: list[Choice] | None = None) -> ChatResponse:
    return ChatResponse(
        intent="penalty_lookup", answer_type="clarify", answer=info.question,
        reason=info.reason, as_of=as_of, options=options or [],
    )


# Mỗi phương án làm rõ trỏ thẳng tới một khung phạt trong catalog. Nhờ vậy
# người dùng chỉ cần bấm một nút, không phải gõ lại câu trả lời.
CLARIFY_PATHS: dict[str, dict[Vehicle, tuple[tuple[str, str], ...]]] = {
    "helmet_role": {
        "xe_may": (
            ("7.2.h", "Tôi là người lái, không đội mũ hoặc cài quai sai"),
            ("7.2.i", "Tôi chở người ngồi sau không đội mũ"),
            ("12.5.b", "Tôi là người ngồi sau, không đội mũ"),
        ),
    },
    "seatbelt_role": {
        "o_to": (
            ("6.3.k", "Tôi là người lái, không thắt dây an toàn"),
            ("6.3.l", "Tôi chở người không thắt dây an toàn"),
            ("12.4", "Tôi là người được chở, không thắt dây an toàn"),
        ),
    },
    "alcohol_level": {
        "xe_may": (
            ("7.6.a", "Chưa vượt quá 0,25 mg/l khí thở (hoặc 50 mg/100 ml máu)"),
            ("7.8.b", "Trên 0,25 đến 0,4 mg/l (hoặc trên 50 đến 80 mg/100 ml)"),
            ("7.9.d", "Trên 0,4 mg/l (hoặc trên 80 mg/100 ml)"),
            ("7.9.đ", "Không chấp hành yêu cầu kiểm tra nồng độ cồn"),
        ),
        "o_to": (
            ("6.6.c", "Chưa vượt quá 0,25 mg/l khí thở (hoặc 50 mg/100 ml máu)"),
            ("6.9.a", "Trên 0,25 đến 0,4 mg/l (hoặc trên 50 đến 80 mg/100 ml)"),
            ("6.11.a", "Trên 0,4 mg/l (hoặc trên 80 mg/100 ml)"),
            ("6.11.b", "Không chấp hành yêu cầu kiểm tra nồng độ cồn"),
        ),
    },
    "alcohol_unit": {
        "xe_may": (
            ("7.6.a", "Chưa vượt quá 0,25 mg/l khí thở (hoặc 50 mg/100 ml máu)"),
            ("7.8.b", "Trên 0,25 đến 0,4 mg/l (hoặc trên 50 đến 80 mg/100 ml)"),
            ("7.9.d", "Trên 0,4 mg/l (hoặc trên 80 mg/100 ml)"),
            ("7.9.đ", "Không chấp hành yêu cầu kiểm tra nồng độ cồn"),
        ),
        "o_to": (
            ("6.6.c", "Chưa vượt quá 0,25 mg/l khí thở (hoặc 50 mg/100 ml máu)"),
            ("6.9.a", "Trên 0,25 đến 0,4 mg/l (hoặc trên 50 đến 80 mg/100 ml)"),
            ("6.11.a", "Trên 0,4 mg/l (hoặc trên 80 mg/100 ml)"),
            ("6.11.b", "Không chấp hành yêu cầu kiểm tra nồng độ cồn"),
        ),
    },
    "speed_excess": {
        "xe_may": (
            ("7.2.b", "Vượt từ 5 đến dưới 10 km/h"),
            ("7.4.a", "Vượt từ 10 đến 20 km/h"),
            ("7.8.a", "Vượt trên 20 km/h"),
        ),
        "o_to": (
            ("6.3.a", "Vượt từ 5 đến dưới 10 km/h"),
            ("6.5.đ", "Vượt từ 10 đến 20 km/h"),
            ("6.6.a", "Vượt trên 20 đến 35 km/h"),
            ("6.7.a", "Vượt trên 35 km/h"),
        ),
    },
    "engine_size": {
        "xe_may": (
            ("18.5.a", "Xe mô tô đến 125 cm³"),
            ("18.7.b", "Xe mô tô trên 125 cm³"),
        ),
    },
    "motorcycle_class": {
        "xe_may": (
            ("18.5.a", "Xe mô tô đến 125 cm³"),
            ("18.7.b", "Xe mô tô trên 125 cm³"),
        ),
    },
    "passenger_count": {
        "xe_may": (
            ("7.2.g", "Chở 2 người (trừ trường hợp được miễn)"),
            ("7.3.b", "Chở từ 3 người trở lên"),
        ),
    },
    "road_type": {
        "o_to": (
            ("6.9.d", "Trong đô thị hoặc đường một chiều"),
            ("6.11.đ", "Trên đường cao tốc"),
        ),
    },
    "license_expiry": {
        "o_to": (
            ("18.8.a", "Bằng lái hết hạn dưới 1 năm"),
            ("18.9.a", "Bằng lái hết hạn từ 1 năm trở lên"),
        ),
    },
    "inspection_expiry": {
        "o_to": (
            ("13.5.a", "Đăng kiểm hết hạn dưới 1 tháng"),
            ("13.6.b", "Đăng kiểm hết hạn từ 1 tháng trở lên"),
        ),
    },
    "accident_cause": {
        "xe_may": (
            ("7.10.b", "Vượt đèn đỏ gây tai nạn"),
            ("7.10.a", "Đi ngược chiều, chạy quá tốc độ hoặc sai làn gây tai nạn"),
        ),
        "o_to": (
            ("6.10.b", "Vượt đèn đỏ hoặc đi ngược chiều gây tai nạn"),
            ("6.10.a", "Chạy quá tốc độ hoặc sai làn gây tai nạn"),
        ),
    },
}


def clarification_options(
    con: sqlite3.Connection, info: Clarification, vehicle: Vehicle, text: str,
) -> list[Choice]:
    """Resolve clarification buttons to concrete catalog records."""
    options: list[Choice] = []
    seen: set[str] = set()
    for path, label in CLARIFY_PATHS.get(info.reason, {}).get(vehicle, ()):
        row = con.execute(
            "SELECT id FROM violations WHERE legal_path = ? AND vehicle_type IN (?, 'both')",
            (path, vehicle),
        ).fetchone()
        if row and row["id"] not in seen:
            seen.add(row["id"])
            options.append(Choice(record_id=row["id"], label=label))
    if options:
        return options
    # Alias qualifiers already use citizen-facing wording (for example the
    # alcohol tiers or speed bands), so reuse them when a direct mapping is
    # not available.
    for alias in find_aliases(con, text):
        matches = alias_record_ids(con, alias["id"], vehicle)
        if len(matches) < 2 or not all(row["qualifier"] for row in matches):
            continue
        for row in matches[:5]:
            if row["record_id"] not in seen:
                seen.add(row["record_id"])
                options.append(Choice(record_id=row["record_id"], label=row["qualifier"]))
        if options:
            break
    return options


def vehicle_penalty_choices(
    con: sqlite3.Connection, surface: str, text: str,
) -> list[Choice]:
    """Preview the same behavior for both vehicles when the user omitted it.

    The first reply then already contains the amounts instead of only asking
    "xe máy hay ô tô"; clicking a preview opens the full penalty record.
    """
    options: list[Choice] = []
    seen: set[str] = set()
    for vehicle, label in (("xe_may", "Xe máy"), ("o_to", "Ô tô")):
        path = direct_path(surface, text, vehicle)
        record = None
        if isinstance(path, str) and path:
            row = con.execute(
                "SELECT id FROM violations WHERE legal_path = ? AND vehicle_type IN (?, 'both')",
                (path, vehicle),
            ).fetchone()
            record = get_record(con, row["id"]) if row else None
        if record is None:
            for alias in find_aliases(con, text):
                matches = alias_record_ids(con, alias["id"], vehicle)
                if len(matches) == 1 and not alias["requires_qualifier"]:
                    record = get_record(con, matches[0]["record_id"])
                    break
        if record and record["id"] not in seen:
            seen.add(record["id"])
            options.append(Choice(
                record_id=record["id"],
                label=f"{label}: {format_range(record['fine_min'], record['fine_max'])}",
            ))
    return options


def penalty_sources(record: dict) -> list[Source]:
    url = record["source_url"]
    if not url or not url.startswith("https://") or not record["source_quote"]:
        return []
    raw = json.loads(record["raw_json"])
    amendment_url = raw.get("source_url_amendment")
    amendments = record["amended_by"]
    locator = legal_path(record)
    if amendment_url == url and amendments:
        prefix = record["source_quote"].split(":", 1)[0]
        location = prefix.removeprefix(amendments[-1]).strip() if prefix.startswith(amendments[-1]) else ""
        return [Source(document=amendments[-1], locator=location or f"Bổ sung {locator}", url=url)]
    sources = [Source(document=record["document"], locator=locator, url=url)]
    if amendment_url and amendments and amendment_url.startswith("https://"):
        sources.append(Source(document=amendments[-1], locator=f"Sửa đổi liên quan đến {locator}", url=amendment_url))
    return sources


def related_choices(con: sqlite3.Connection, record: dict) -> list[Choice]:
    """Find the same behavior for the other vehicle type, when an alias links both."""
    if record["vehicle_type"] == "both":
        return []
    rows = con.execute(
        """
        SELECT ar2.record_id, ar2.vehicle_type, ar2.qualifier,
               ar1.qualifier AS source_qualifier
        FROM alias_records ar1
        JOIN alias_records ar2 ON ar1.alias_id = ar2.alias_id
        WHERE ar1.record_id = ?
          AND ar2.record_id != ?
          AND ar2.vehicle_type IN ('xe_may', 'o_to')
          AND ar2.vehicle_type != ?
        ORDER BY ar2.vehicle_type, ar2.record_id
        """,
        (record["id"], record["id"], record["vehicle_type"]),
    ).fetchall()
    if rows and rows[0]["source_qualifier"]:
        same_level = [row for row in rows if row["qualifier"] == rows[0]["source_qualifier"]]
        if same_level:
            rows = same_level
    if len({row["record_id"] for row in rows}) != 1:
        # A broad alias group (for example vehicle equipment) can contain
        # several different behaviors. Do not guess which one the user means.
        return []
    row = rows[0]
    label = f"Xem mức phạt cho {VEHICLE_LABELS[row['vehicle_type']]}"
    if row["qualifier"]:
        label += f" — {row['qualifier']}"
    return [Choice(record_id=row["record_id"], label=label)]


def penalty_guidance(
    con: sqlite3.Connection, as_of: str, sources: list[Source], include_payment: bool,
) -> list[Guidance]:
    """Append the standard payment/complaint steps and their citations.

    The catalog stores fines, but a citizen also needs to know what to do after
    receiving the decision. These chunks come from the same procedure corpus
    used by the procedure branch, so every sentence stays traceable. Records
    without a fine still get the complaint deadline.
    """
    indices = {
        (source.document, source.locator, source.url, tuple(source.pages)): index
        for index, source in enumerate(sources, 1)
    }
    chunk_ids = ("nop-thoi-han", "nop-dia-diem") if include_payment else ()
    items: list[Guidance] = []
    for chunk_id in (*chunk_ids, "kn-thoi-hieu"):
        chunk = con.execute(
            "SELECT * FROM procedures WHERE id = ? AND as_of = ?", (chunk_id, as_of),
        ).fetchone()
        if chunk is None:
            continue
        refs = con.execute(
            """
            SELECT s.number, s.url, c.locator, c.pages
            FROM procedure_citations c JOIN procedure_sources s ON s.id = c.source_id
            WHERE c.procedure_id = ? ORDER BY c.position
            """,
            (chunk["id"],),
        ).fetchall()
        if not refs or any(not row["url"].startswith("https://") for row in refs):
            continue
        marks: list[str] = []
        for row in refs:
            pages = json.loads(row["pages"]) if row["pages"] else []
            key = (row["number"], row["locator"], row["url"], tuple(pages))
            if key not in indices:
                sources.append(Source(document=row["number"], locator=row["locator"], url=row["url"], pages=pages))
                indices[key] = len(sources)
            marks.append(f"[{indices[key]}]")
        items.append(Guidance(title=chunk["title"], text=f"{chunk['text']} {' '.join(marks)}"))
    return items


def penalty_response(
    con: sqlite3.Connection, record: dict, as_of: str, text: str,
    related: list[Choice] | None = None,
) -> ChatResponse:
    sources = penalty_sources(record)
    if not sources:
        return refuse(as_of, "insufficient_source", "Mình chưa có căn cứ nguồn cho trường hợp này.", "penalty_lookup")
    amendment = sources[1] if len(sources) > 1 else None
    guidance = penalty_guidance(
        con, as_of, sources, include_payment=record["record_kind"] == "fine",
    )
    fine = Fine(
        min=record["fine_min"], max=record["fine_max"],
        unit=record.get("fine_unit"), cap=record.get("fine_cap"),
    )
    organization_fine = (
        Fine(
            min=record["fine_org_min"], max=record["fine_org_max"],
            unit=record.get("fine_unit"), cap=record.get("fine_org_cap"),
        )
        if record["fine_org_min"] is not None else None
    )
    penalty = Penalty(
        record_id=record["id"], vehicle_type=record["vehicle_type"], subject=record["subject"],
        record_kind=record["record_kind"], behavior=record["behavior_text"], legal_path=record["legal_path"],
        fine=fine, organization_fine=organization_fine, license_points=record["license_points"],
        license_points_condition=record["license_points_condition"],
        license_point_tiers=[
            LicensePointTier(points=value["points"], condition=value["condition"])
            for value in (record.get("license_point_tiers") or [])
        ],
        additional_penalties=[format_penalty(value) for value in record["additional_penalties"]],
        remedial_measures=[format_penalty(value) for value in record["remedial_measures"]],
        guidance=guidance,
        verification_status=record["verification_status"],
        source_quote=record["source_quote"],
    )

    def fine_with_unit(value: Fine) -> str:
        text = format_range(value.min, value.max)
        if value.unit == "per_person":
            text += " cho mỗi người vượt quá quy định"
        if value.cap is not None:
            text += f", tổng mức phạt tối đa {format_money(value.cap)}"
        return text

    if penalty.record_kind == "warning":
        lines = ["Hình thức xử phạt: cảnh cáo."]
    elif penalty.record_kind == "additional_only":
        lines = ["Mức phạt tiền: không áp dụng cho bản ghi này."]
    elif organization_fine is not None:
        individual = f"Mức phạt cá nhân: {fine_with_unit(fine)}."
        organization = f"Mức phạt tổ chức: {fine_with_unit(organization_fine)}."
        lines = [organization, individual] if includes(r"\b(?:cong ty|to chuc|doanh nghiep)\b", text) else [individual, organization]
    else:
        lines = [f"Mức phạt tiền: {fine_with_unit(fine)}."]
    if penalty.license_point_tiers:
        tiers = "; ".join(
            f"trừ {tier.points} điểm nếu {tier.condition}"
            for tier in penalty.license_point_tiers
        )
        lines.append(f"Trừ điểm GPLX: {tiers}.")
    else:
        lines.append(f"Trừ điểm GPLX: {penalty.license_points} điểm" + (
            f" nếu {penalty.license_points_condition}." if penalty.license_points_condition else "."
        ))
    if penalty.additional_penalties:
        lines.append("Hình phạt bổ sung: " + "; ".join(penalty.additional_penalties) + ".")
    if penalty.remedial_measures:
        lines.append("Biện pháp khắc phục: " + "; ".join(penalty.remedial_measures) + ".")
    lines.append(f"Căn cứ: {legal_path(record)} Nghị định {record['document']} [1].")
    if amendment:
        lines.append(f"Văn bản sửa đổi: {amendment.document} [2].")
    if guidance:
        lines.append("Nộp phạt và khiếu nại:")
        lines.extend(f"{item.title}: {item.text}" for item in guidance)
    return ChatResponse(
        intent="penalty_lookup", answer_type="penalty", answer="\n".join(lines),
        as_of=as_of, penalty=penalty, related=related or [], sources=sources,
    )


COMPLAINT_TOPICS = (
    (r"\brut\b", "kn-rut-don"),
    (r"\b(?:tam (?:dung|dinh chi)|van phai nop|phai nop tien|dang khieu nai.{0,35}(?:nop|dong))\b", "kn-van-phai-nop"),
    (r"\b(?:uy quyen|dai dien|nguoi nha.{0,20}thay)\b", "kn-dai-dien"),
    (r"\b(?:khong thu ly|may ngay lam viec.{0,20}thu ly|bao lau.{0,20}thu ly|duoc thu ly)\b", "kn-thu-ly"),
    (r"\b(?:khong dong y|het han giai quyet lan dau|don khieu nai lan hai|khieu nai tiep)\b", "kn-lan-hai"),
    (r"\b(?:thoi hieu|90 ngay|nam vien|tro ngai|con bao nhieu ngay)\b", "kn-thoi-hieu"),
    (r"\blan hai\b.*\b(?:giai quyet|thu ly|phuc tap)\b|\b(?:giai quyet|thu ly)\b.*\blan hai\b", "kn-giai-quyet-lan-hai"),
    (r"\b(?:khieu nai lan hai|cap tren)\b", "kn-lan-hai"),
    (r"\b(?:giai quyet|phuc tap)\b.*\blan dau\b|\blan dau\b.*\b(?:giai quyet|phuc tap)\b", "kn-giai-quyet-lan-dau"),
    (r"\b(?:trinh bay truc tiep|khieu nai truc tiep|trinh bay tai|bat buoc.{0,12}lam don)\b", "kn-hinh-thuc"),
    (r"\b(?:ho so|bang chung|can ghi|noi dung don|dinh kem|viet don)\b", "kn-noi-dung-don"),
    (r"\b(?:lan dau|toi ai|cho ai|nguoi ky|gui.{0,20}o dau)\b", "kn-lan-dau"),
)

PAYMENT_TOPICS = (
    (r"\b(?:cham nop|tre han|qua han|nop muon|0 05)\b", "nop-cham"),
    (r"\b(?:nhieu lan|chia dot|tra gop|may dot)\b", "nop-nhieu-lan"),
    (r"\b(?:xin hoan|duoc hoan|hoan thi hanh)\b", "nop-hoan"),
    (r"\b(?:xin giam|xin mien|giam hoac mien|don.{0,10}mien)\b", "nop-giam-mien"),
    (r"\b(?:nop tai cho|dong tai cho|khong lap bien ban)\b", "nop-tai-cho"),
    (r"\b(?:buu dien|buu chinh cong ich|buu cuc)\b", "nop-buu-chinh"),
    (r"\b(?:bien lai|chung tu|chung minh gi)\b", "nop-chung-tu"),
    (r"\b(?:nhan (?:lai )?(?:giay to|bang lai)|tra lai giay to|giu giay to.{0,65}nhan lai)\b", "nop-nhan-giay-to"),
    (r"\b(?:so bien ban|ma quyet dinh|bieu mau tra cuu|can dien gi)\b", "nop-tra-cuu-quyet-dinh"),
    (r"\b(?:online|truc tuyen|qua mang|cong dich vu cong)\b", "nop-truc-tuyen"),
)
PAYMENT_LOCATION = r"\b(?:o dau|noi nop|chuyen khoan|so tai khoan|kho bac|ngan hang)\b"
PAYMENT_DEADLINE = r"\b(?:bao lau|may ngay|thoi han|han nop|nhan quyet dinh roi)\b"
GENERAL_PROCEDURE = r"\b(?:lam sao|lam the nao|the nao|thu tuc|quy trinh|huong dan|cach)\b"
PAYMENT_CUE = (
    r"\b(?:nop tien|chuyen khoan|thanh toan|dong tai cho|nop qua|nop nhieu lan"
    r"|hoan thi hanh|0 05|tra mot phan|thoi han thi hanh)\b"
)


def procedure_targets(text: str) -> tuple[str, list[str]]:
    complaint = includes(r"\b(?:khieu nai|phat oan|phat nham|tam dinh chi)\b", text)
    topic = "khieu_nai" if complaint else "nop_phat"
    for pattern, chunk in COMPLAINT_TOPICS if complaint else PAYMENT_TOPICS:
        if includes(pattern, text):
            return topic, [chunk]
    if not complaint:
        chunks = []
        if includes(PAYMENT_LOCATION, text):
            chunks.append("nop-dia-diem")
        if includes(PAYMENT_DEADLINE, text):
            chunks.append("nop-thoi-han")
        if chunks:
            return topic, chunks
    if includes(GENERAL_PROCEDURE, text):
        return topic, (
            ["kn-lan-dau", "kn-noi-dung-don", "kn-thoi-hieu"]
            if complaint else ["nop-dia-diem", "nop-thoi-han", "nop-truc-tuyen"]
        )
    return topic, []


def procedure_response(con: sqlite3.Connection, surface: str, text: str, as_of: str) -> ChatResponse:
    topic, ids = procedure_targets(text)
    if ids:
        chunks = [con.execute("SELECT * FROM procedures WHERE id = ? AND topic = ?", (rid, topic)).fetchone()
                  for rid in ids]
    else:
        # A generic intent word alone is insufficient evidence for a BM25 hit.
        # Look for overlap with a heading after removing common intent terms.
        ignored = {"khieu", "nai", "nop", "dong", "tien", "phat", "quyet", "dinh", "toi", "gi", "co"}
        terms = set(text.split()) - ignored
        chunks = [
            row for row in search_procedures(con, surface, 5)
            if row["topic"] == topic and len(terms.intersection(normalize_text(row["title"]).split())) >= 2
        ][:1]

    sources: list[Source] = []
    paragraphs: list[str] = []
    matched_ids: list[str] = []
    source_indices: dict[tuple, int] = {}
    for chunk in chunks:
        if chunk is None or chunk["as_of"] != as_of:
            continue
        refs = con.execute(
            """
            SELECT s.number, s.url, c.locator, c.pages
            FROM procedure_citations c JOIN procedure_sources s ON s.id = c.source_id
            WHERE c.procedure_id = ? ORDER BY c.position
            """,
            (chunk["id"],),
        ).fetchall()
        if not refs or any(not row["url"].startswith("https://") for row in refs):
            continue
        marks = []
        for row in refs:
            pages = json.loads(row["pages"]) if row["pages"] else []
            key = (row["number"], row["locator"], row["url"], tuple(pages))
            if key not in source_indices:
                sources.append(Source(document=row["number"], locator=row["locator"], url=row["url"], pages=pages))
                source_indices[key] = len(sources)
            marks.append(f"[{source_indices[key]}]")
        paragraphs.append(f"{chunk['title']}\n{chunk['text']} {' '.join(marks)}")
        matched_ids.append(chunk["id"])
    if not paragraphs:
        return refuse(as_of, "insufficient_source", "Mình chưa tìm thấy hướng dẫn có căn cứ cho câu hỏi này.", "procedure")
    return ChatResponse(
        intent="procedure", answer_type="procedure", answer="\n\n".join(paragraphs),
        as_of=as_of, sources=sources, procedure_ids=matched_ids,
    )


def lookup_penalty(
    con: sqlite3.Connection, surface: str, text: str, vehicle: Vehicle, as_of: str,
) -> ChatResponse:
    parts = re.split(r"\b(?:va|dong thoi)\b", surface)
    if len(parts) > 1:
        part_paths = [direct_path(part, normalize_text(part), vehicle) for part in parts]
        if sum(isinstance(item, str) and bool(item) for item in part_paths) > 1:
            options: list[Choice] = []
            for part, item in zip(parts, part_paths):
                if not isinstance(item, str) or not item:
                    continue
                row = con.execute(
                    "SELECT id, behavior_text FROM violations WHERE legal_path = ? AND vehicle_type IN (?, 'both')",
                    (item, vehicle),
                ).fetchone()
                if row:
                    options.append(Choice(record_id=row["id"], label=row["behavior_text"]))
            return clarify(
                as_of,
                Clarification("multiple_violations", "Bạn muốn tra hành vi nào trước?"),
                options,
            )
    path = direct_path(surface, text, vehicle)
    if isinstance(path, Clarification):
        return clarify(as_of, path, clarification_options(con, path, vehicle, text))
    if path is not None:
        row = con.execute(
            "SELECT id FROM violations WHERE legal_path = ? AND vehicle_type IN (?, 'both')",
            (path, vehicle),
        ).fetchone()
        record = get_record(con, row["id"]) if row else None
        if record:
            return penalty_response(con, record, as_of, text, related_choices(con, record))
        return refuse(as_of, "insufficient_source", "Mình chưa có khung phạt phù hợp trong catalog.", "penalty_lookup")

    for alias in find_aliases(con, text):
        alias_id = alias["id"]
        matches = alias_record_ids(con, alias_id, vehicle)
        if not matches:
            continue
        if alias_id == "vuot-den-do":
            return clarify(as_of, Clarification("conduct", "Bạn mô tả cụ thể đã đi qua đèn đỏ hay vi phạm tín hiệu khác?"))
        if len(matches) == 1 and not alias["requires_qualifier"]:
            record = get_record(con, matches[0]["record_id"])
            if record:
                return penalty_response(con, record, as_of, text, related_choices(con, record))
        options = [Choice(record_id=row["record_id"], label=row["qualifier"])
                   for row in matches[:3] if row["qualifier"]]
        return clarify(as_of, Clarification("conduct", "Bạn mô tả rõ hơn trường hợp vi phạm để mình chọn đúng khung phạt?"), options)

    results = fts_search(con, text, vehicle, 3)
    if results:
        options = [Choice(record_id=row["id"], label=row["behavior_text"]) for row in results]
        return clarify(as_of, Clarification("conduct", "Bạn cho biết tình huống nào trong các hành vi gần nhất đúng với trường hợp của bạn?"), options)
    return refuse(as_of, "insufficient_source", "Mình chưa tìm thấy hành vi khớp có căn cứ trong catalog.", "penalty_lookup")


def chat(con: sqlite3.Connection, request: ChatRequest) -> ChatResponse:
    as_of = snapshot(con)
    surface, text = normalize_question(request.question)
    if request.record_id:
        record = get_record(con, request.record_id)
        if record is None:
            return refuse(
                as_of, "record_not_found",
                "Không tìm thấy bản ghi phù hợp trong catalog. Bạn thử mô tả lại hành vi.",
                "penalty_lookup",
            )
        if request.vehicle_type and record["vehicle_type"] not in (request.vehicle_type, "both"):
            return clarify(
                as_of,
                Clarification("vehicle_type", "Bản ghi này thuộc loại xe khác. Bạn muốn tra cho xe máy hay ô tô?"),
            )
        return penalty_response(con, record, as_of, text, related_choices(con, record))
    mentioned = mentioned_vehicles(text)
    if includes(OUTSIDE_REQUEST, text):
        return refuse(as_of, "out_of_scope", "Mình hỗ trợ tra mức phạt xe máy, ô tô và hướng dẫn nộp phạt, khiếu nại giao thông.")
    if includes(OUTSIDE_VEHICLE, text) and (
        not mentioned or includes(r"(?:^|\b(?:lai|di|chay|dieu khien) )" + OUTSIDE_VEHICLE, text)
    ):
        return refuse(as_of, "vehicle_out_of_scope", "Phạm vi tra cứu mức phạt hiện gồm xe máy và ô tô cá nhân.")
    if includes(PROCEDURE, text) or (includes(PAYMENT_CUE, text) and includes(r"\b(?:phat|quyet dinh)\b", text)):
        return procedure_response(con, surface, text, as_of)
    if includes(HISTORICAL, text) or re.search(r"\b\d{1,2}/\d{1,2}/\d{4}\b", surface):
        return refuse(as_of, "historical_lookup_unsupported", "Catalog chỉ hỗ trợ tra cứu theo ngày snapshot hiển thị trong kết quả.")
    if not mentioned and request.vehicle_type is None and not (
        includes(r"\b(?:phat|vi pham|tru diem|vuot den|nguoc chieu|giao xe|sang ten)\b", text)
        or includes(LICENSE, text) or find_aliases(con, text)
    ):
        return refuse(as_of, "out_of_scope", "Mình hỗ trợ câu hỏi về mức phạt giao thông, nộp phạt và khiếu nại.")
    if len(mentioned) > 1 or (mentioned and request.vehicle_type and request.vehicle_type not in mentioned):
        return clarify(as_of, Clarification("vehicle_type", "Bạn muốn tra cho xe máy hay ô tô?"))
    vehicle = request.vehicle_type or next(iter(mentioned), None)
    if vehicle is None:
        return clarify(
            as_of,
            Clarification("vehicle_type", "Bạn đi xe máy hay ô tô?"),
            vehicle_penalty_choices(con, surface, text),
        )
    return lookup_penalty(con, surface, text, vehicle, as_of)
