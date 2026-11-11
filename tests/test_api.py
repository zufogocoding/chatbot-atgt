import asyncio
from contextlib import closing
from datetime import datetime, timedelta
from pathlib import Path
import re
import sqlite3
from tempfile import TemporaryDirectory

import httpx
import pytest

from src.api.main import app, create_app


def call(method: str, path: str, payload: dict | None = None, application=app) -> httpx.Response:
    async def request() -> httpx.Response:
        transport = httpx.ASGITransport(app=application)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, json=payload)

    return asyncio.run(request())


def ask(question: str, vehicle_type: str | None = None) -> dict:
    body = {"question": question}
    if vehicle_type:
        body["vehicle_type"] = vehicle_type
    response = call("POST", "/chat", body)
    assert response.status_code == 200
    return response.json()


def test_health_and_openapi():
    response = call("GET", "/health")
    assert response.status_code == 200
    assert response.json()["violations"] > 0
    assert response.json()["procedures"] > 0
    assert "/chat" in call("GET", "/openapi.json").json()["paths"]


def test_question_log_records_resolved_answer_and_masks_identifiers(monkeypatch, tmp_path):
    path = tmp_path / "logs" / "questions.db"
    monkeypatch.setenv("ATGT_QUESTION_LOG_PATH", str(path))
    application = create_app()

    response = call("POST", "/chat", {
        "question": "Xe máy vượt đèn đỏ (59-X1 123.45, 0912 345 678, vi-du@example.com, 012345678901)",
        "record_id": "nd168-d7-k7-c",
    }, application)
    assert response.status_code == 200

    response = call("POST", "/chat", {
        "question": "Vượt đèn đỏ phạt bao nhiêu?",
    }, application)
    assert response.status_code == 200

    with closing(sqlite3.connect(path)) as connection:
        rows = connection.execute("SELECT * FROM question_log ORDER BY rowid").fetchall()
    assert [row[:-1] for row in rows] == [
        ("Xe máy vượt đèn đỏ ([đã ẩn], [đã ẩn], [đã ẩn], [đã ẩn])", "penalty", "nd168-d7-k7-c", None),
        ("Vượt đèn đỏ phạt bao nhiêu?", "clarify", None, "vehicle_type"),
    ]
    assert all(datetime.fromisoformat(row[-1]).utcoffset() == timedelta(0) for row in rows)


def test_question_log_unavailable_does_not_break_chat(monkeypatch, tmp_path):
    monkeypatch.setenv("ATGT_QUESTION_LOG_PATH", str(tmp_path))
    response = call("POST", "/chat", {"question": "Xe máy vượt đèn đỏ"}, create_app())
    assert response.status_code == 200
    assert response.json()["answer_type"] == "penalty"


@pytest.mark.parametrize(
    "question, record_id, minimum, maximum",
    [
        ("Xe máy vượt đèn đỏ gây tai nạn", "nd168-d7-k10-b", 10_000_000, 14_000_000),
        ("Ô tô vượt đèn đỏ nhưng không gây tai nạn", "nd168-d6-k9-b", 18_000_000, 20_000_000),
        ("Ô tô chạy quá tốc độ 20 km/h", "nd168-d6-k5-đ", 4_000_000, 6_000_000),
        ("Ô tô chạy quá tốc độ 20,1 km/h", "nd168-d6-k6-a", 6_000_000, 8_000_000),
        ("Đi xe máy đo nồng độ cồn 0,25 mg/l khí thở", "nd168-d7-k6-a", 2_000_000, 3_000_000),
        ("Đi xe máy đo nồng độ cồn 0,251 mg/l khí thở", "nd168-d7-k8-b", 6_000_000, 8_000_000),
        ("Ô tô cầm điện thoại khi lái xe", "nd168-d6-k5-h", 4_000_000, 6_000_000),
        ("Ô tô chuyển làn ngoài cao tốc không giữ khoảng cách an toàn", "nd168-d6-k2-a", 600_000, 800_000),
        ("Người ngồi sau xe máy không đội mũ bảo hiểm", "nd168-d12-k5-b", 400_000, 600_000),
        ("Hành khách trên ô tô không thắt dây an toàn", "nd168-d12-k4", 350_000, 400_000),
        ("Người ngồi sau che dù khi đi xe máy", "nd168-d12-k2-d", 200_000, 250_000),
        ("Người ngồi sau xe máy bám kéo xe khác", "nd168-d12-k5-a", 400_000, 600_000),
    ],
)
def test_penalty_boundaries_and_sources(question, record_id, minimum, maximum):
    reply = ask(question)
    assert reply["answer_type"] == "penalty"
    assert reply["penalty"]["record_id"] == record_id
    assert reply["penalty"]["fine"]["min"] == minimum
    assert reply["penalty"]["fine"]["max"] == maximum
    assert reply["penalty"]["fine"]["unit"] is None
    assert reply["penalty"]["fine"]["cap"] is None
    assert reply["sources"][0]["url"].startswith("https://")
    assert "[1]" in reply["answer"]


def test_organization_fine():
    reply = ask("Công ty mua ô tô mà chưa sang tên")
    assert reply["penalty"]["organization_fine"]["min"] == 8_000_000
    assert reply["penalty"]["organization_fine"]["max"] == 12_000_000
    assert reply["answer"].startswith("Mức phạt tổ chức")


def test_per_person_fine_and_licence_point_tiers():
    reply = call("POST", "/chat", {
        "question": "Xem mức phạt cho chủ xe",
        "record_id": "nd168-d32-k5",
    }).json()
    assert reply["answer_type"] == "penalty"
    assert reply["penalty"]["record_id"] == "nd168-d32-k5"
    fine = reply["penalty"]["fine"]
    assert (fine["min"], fine["max"], fine["unit"], fine["cap"]) == (
        800_000, 1_200_000, "per_person", 75_000_000,
    )
    assert reply["penalty"]["organization_fine"]["cap"] == 150_000_000
    assert "mỗi người vượt quá" in reply["answer"]
    assert "75.000.000" in reply["answer"]
    assert [(tier["points"]) for tier in reply["penalty"]["license_point_tiers"]] == [4, 10]


def test_penalty_includes_legal_quote():
    reply = ask("Xe máy vượt đèn đỏ")
    assert reply["penalty"]["record_id"] == "nd168-d7-k7-c"
    assert "Không chấp hành hiệu lệnh" in reply["penalty"]["source_quote"]
    assert "4.000.000" in reply["penalty"]["source_quote"]


def test_penalty_includes_payment_and_complaint_guidance():
    reply = ask("Xe máy vượt đèn đỏ")
    guidance = reply["penalty"]["guidance"]
    assert len(guidance) == 3
    body = " ".join(item["text"] for item in guidance)
    assert "10 ngày" in body
    assert "Kho bạc" in body
    assert "90 ngày" in body
    markers = {int(value) for value in re.findall(r"\[(\d+)\]", body)}
    assert markers and max(markers) <= len(reply["sources"])

    # Records without a fine have nothing to pay, but still carry the
    # complaint deadline.
    warning = call("POST", "/chat", {
        "question": "Xem", "record_id": "nd168-d18-k1",
    }).json()
    assert warning["penalty"]["record_kind"] == "warning"
    assert [item["title"] for item in warning["penalty"]["guidance"]] == ["Thời hiệu khiếu nại lần đầu"]


def test_related_vehicle_and_option_selection():
    reply = ask("Xe máy vượt đèn đỏ")
    related = {item["record_id"]: item for item in reply["related"]}
    assert "nd168-d6-k9-b" in related
    assert "ô tô" in related["nd168-d6-k9-b"]["label"]

    selected = call("POST", "/chat", {
        "question": "Xem mức phạt cho ô tô",
        "record_id": "nd168-d6-k9-b",
    }).json()
    assert selected["answer_type"] == "penalty"
    assert selected["penalty"]["record_id"] == "nd168-d6-k9-b"
    assert selected["penalty"]["vehicle_type"] == "o_to"
    assert selected["related"][0]["record_id"] == "nd168-d7-k7-c"


def test_related_vehicle_matches_qualifier_and_skips_broad_groups():
    alcohol = ask("Đi xe máy đo nồng độ cồn 0,25 mg/l khí thở")
    assert alcohol["penalty"]["record_id"] == "nd168-d7-k6-a"
    assert [item["record_id"] for item in alcohol["related"]] == ["nd168-d6-k6-c"]
    assert "chưa vượt quá" in alcohol["related"][0]["label"]

    # "Thiếu gương" is part of a broad equipment alias that maps to several
    # different car behaviors, so no single comparison is safe to offer.
    equipment = ask("Xe máy không có gương chiếu hậu")
    assert equipment["penalty"]["record_id"] == "nd168-d14-k1-a"
    assert equipment["related"] == []


def test_option_selection_requires_valid_record_and_vehicle():
    missing = call("POST", "/chat", {
        "question": "Xem", "record_id": "nd168-does-not-exist",
    }).json()
    assert missing["answer_type"] == "refuse"
    assert missing["reason"] == "record_not_found"

    wrong_vehicle = call("POST", "/chat", {
        "question": "Xem", "record_id": "nd168-d7-k7-c", "vehicle_type": "o_to",
    }).json()
    assert wrong_vehicle["answer_type"] == "clarify"
    assert wrong_vehicle["reason"] == "vehicle_type"


def test_vehicle_question_previews_both_fines_before_asking():
    reply = ask("Vượt đèn đỏ phạt bao nhiêu?")
    assert reply["answer_type"] == "clarify"
    assert reply["reason"] == "vehicle_type"
    labels = {option["record_id"]: option["label"] for option in reply["options"]}
    assert set(labels) == {"nd168-d7-k7-c", "nd168-d6-k9-b"}
    assert "Xe máy" in labels["nd168-d7-k7-c"]
    assert "4.000.000" in labels["nd168-d7-k7-c"]
    assert "Ô tô" in labels["nd168-d6-k9-b"]
    assert "18.000.000" in labels["nd168-d6-k9-b"]

    chosen = call("POST", "/chat", {
        "question": labels["nd168-d6-k9-b"], "record_id": "nd168-d6-k9-b",
    }).json()
    assert chosen["answer_type"] == "penalty"
    assert chosen["penalty"]["record_id"] == "nd168-d6-k9-b"


def test_common_vehicle_unspecified_questions_show_amounts():
    phone = ask("Sử dụng điện thoại khi lái xe phạt bao nhiêu?")
    assert phone["reason"] == "vehicle_type"
    assert {option["record_id"] for option in phone["options"]} == {
        "nd168-d7-k4-đ", "nd168-d6-k5-h",
    }
    seatbelt = ask("Không thắt dây an toàn phạt bao nhiêu?")
    assert seatbelt["reason"] == "vehicle_type"
    assert [option["record_id"] for option in seatbelt["options"]] == ["nd168-d6-k3-k"]


def test_passenger_count_question_offers_both_bands():
    reply = ask("Xe máy chở quá số người bị phạt bao nhiêu?")
    assert reply["answer_type"] == "clarify"
    assert reply["reason"] == "passenger_count"
    assert {option["record_id"] for option in reply["options"]} == {
        "nd168-d7-k2-g", "nd168-d7-k3-b",
    }


def test_owner_change_questions_answer_directly():
    assert ask("Xe máy không sang tên bị phạt bao nhiêu?")["penalty"]["record_id"] == "nd168-d32-k3-a"
    assert ask("Ô tô không sang tên bị phạt bao nhiêu?")["penalty"]["record_id"] == "nd168-d32-k7-h"
    generic = ask("Không sang tên xe bị phạt bao nhiêu?")
    assert generic["answer_type"] == "clarify"
    assert generic["reason"] == "vehicle_type"
    assert {option["record_id"] for option in generic["options"]} == {
        "nd168-d32-k3-a", "nd168-d32-k7-h",
    }


def test_motorcycle_class_clarification_offers_engine_choices():
    reply = ask("Xe gắn máy 50cc không có bằng lái")
    assert reply["answer_type"] == "clarify"
    assert reply["reason"] == "motorcycle_class"
    assert {option["record_id"] for option in reply["options"]} == {
        "nd168-d18-k5-a", "nd168-d18-k7-b",
    }


def test_passenger_is_a_separate_subject():
    passenger = ask("Người ngồi sau xe máy không đội mũ bảo hiểm")
    assert passenger["penalty"]["subject"] == "nguoi_duoc_cho"
    assert passenger["penalty"]["behavior"].startswith("Không đội")
    driver = ask("Xe máy chở người không đội mũ bảo hiểm")
    assert driver["penalty"]["record_id"] == "nd168-d7-k2-i"
    assert driver["penalty"]["subject"] == "nguoi_dieu_khien"


@pytest.mark.parametrize(
    "question, record_id",
    [
        ("Xe máy chở ba người phía sau", "nd168-d7-k3-b"),
        ("Xe máy chở 3 người phía sau", "nd168-d7-k3-b"),
        ("Xe máy chở hai người lớn", "nd168-d7-k2-g"),
        ("Xe máy chở 2 người lớn", "nd168-d7-k2-g"),
        ("Xe máy không có gương chiếu hậu", "nd168-d14-k1-a"),
        ("Xe máy thiếu gương chiếu hậu bên trái", "nd168-d14-k1-a"),
        ("Ô tô chuyển làn không xi nhan", "nd168-d6-k2-a"),
        ("Ô tô không có kính chắn gió", "nd168-d13-k1"),
        ("Ô tô lắp thêm đèn", "nd168-d13-k3-a"),
        ("Ô tô lốp không đúng kích cỡ", "nd168-d13-k3-c"),
        ("Ô tô phanh không ăn", "nd168-d13-k5-b"),
        ("Xe máy phanh không ăn", "nd168-d14-k1-d"),
        ("Ô tô còi quá to", "nd168-d13-k5-d"),
        ("Xe máy còi quá to", "nd168-d14-k2-đ"),
        ("Ô tô không có bộ giảm thanh", "nd168-d13-k2-c"),
        ("Xe máy không có bộ giảm thanh", "nd168-d14-k2-d"),
        ("Ô tô dán logo cơ quan nhà nước", "nd168-d13-k4-c"),
        ("Xe máy lắp đèn chiếu sáng phía sau", "nd168-d14-k1-đ"),
        ("Xe máy bấm còi ban đêm", "nd168-d7-k1-i"),
        ("Ô tô bấm còi sau 22 giờ", "nd168-d6-k1-đ"),
        ("Xe máy không chấp hành biển báo", "nd168-d7-k1-a"),
        ("Ô tô đi sai vạch kẻ đường", "nd168-d6-k1-a"),
        ("Ô tô đi lên vỉa hè", "nd168-d6-k6-d"),
        ("Xe máy chạy dưới tốc độ tối thiểu", "nd168-d7-k1-k"),
        ("Ô tô không nhường xe cứu hỏa", "nd168-d6-k6-b"),
        ("Xe máy cản trở xe ưu tiên", "nd168-d7-k7-đ"),
    ],
)
def test_common_phrasings(question, record_id):
    reply = ask(question)
    assert reply["answer_type"] == "penalty"
    assert reply["penalty"]["record_id"] == record_id


def test_right_of_way_without_vehicle_asks_for_vehicle():
    reply = ask("Không nhường đường cho xe ưu tiên")
    assert reply["answer_type"] == "clarify"
    assert reply["reason"] == "vehicle_type"


@pytest.mark.parametrize(
    "question, source_id",
    [
        ("Nộp phạt giao thông trực tuyến thế nào?", "nop-truc-tuyen"),
        ("Thời hiệu khiếu nại quyết định xử phạt bao lâu?", "kn-thoi-hieu"),
        ("Đang khiếu nại quyết định xử phạt thì vẫn phải nộp tiền không?", "kn-van-phai-nop"),
    ],
)
def test_procedure_has_source(question, source_id):
    reply = ask(question)
    assert reply["answer_type"] == "procedure"
    assert source_id in reply["procedure_ids"]
    assert reply["sources"] and all(source["locator"] for source in reply["sources"])
    assert "[1]" in reply["answer"]
    assert reply["penalty"] is None


def test_payment_where_and_deadline():
    reply = ask("Nộp phạt ở đâu, thời hạn bao lâu?")
    assert set(reply["procedure_ids"]) == {"nop-dia-diem", "nop-thoi-han"}
    assert len(reply["sources"]) > 1
    assert "nop-thoi-han" in ask("Nộp phạt bao lâu nếu nhận quyết định ngày 05/11/2026?")["procedure_ids"]


@pytest.mark.parametrize(
    "question, answer_type, reason",
    [
        ("Vượt đèn đỏ phạt bao nhiêu?", "clarify", "vehicle_type"),
        ("Ô tô chạy quá tốc độ thì phạt bao nhiêu?", "clarify", "speed_excess"),
        ("Ô tô có nồng độ cồn 0,3 thì phạt bao nhiêu?", "clarify", "alcohol_unit"),
        ("Xe gắn máy 50cc không có bằng lái", "clarify", "motorcycle_class"),
        ("Xe máy vượt đèn đỏ và đi ngược chiều trên đường một chiều", "clarify", "multiple_violations"),
        ("Xe buýt vượt đèn đỏ", "refuse", "vehicle_out_of_scope"),
        ("Xe máy chuyên dùng đi trên đường", "refuse", "vehicle_out_of_scope"),
        ("Ô tô đang đỗ mà cầm điện thoại có bị phạt không?", "refuse", "insufficient_source"),
        ("Tôi chạy xe máy không vượt đèn đỏ thì phạt bao nhiêu?", "refuse", "insufficient_source"),
        ("Tháng 6 năm 2024 xe máy vượt đèn đỏ phạt bao nhiêu?", "refuse", "historical_lookup_unsupported"),
    ],
)
def test_guardrails_do_not_return_amount(question, answer_type, reason):
    reply = ask(question)
    assert reply["answer_type"] == answer_type
    assert reply["reason"] == reason
    assert reply["penalty"] is None
    assert reply["sources"] == []


@pytest.mark.parametrize(
    "question, record_id",
    [
        ("Xe khách vượt đèn đỏ bị phạt bao nhiêu?", "nd168-d6-k9-b"),
        ("Xe tải vượt đèn đỏ", "nd168-d6-k9-b"),
        ("Tôi lái ô tô tải vượt đèn đỏ", "nd168-d6-k9-b"),
        ("Lái xe tải vượt đèn đỏ bị phạt bao nhiêu?", "nd168-d6-k9-b"),
        ("xe khach vuot den do bi phat bn?", "nd168-d6-k9-b"),
        ("Chủ xe đầu kéo không lắp thiết bị giám sát hành trình bị phạt bao nhiêu?", "nd168-d32-k9a-a"),
        ("Xe đầu kéo làm sai lệch dữ liệu giám sát hành trình bị phạt thế nào?", "nd168-d32-k9a-a"),
    ],
)
def test_commercial_vehicle_questions_route_like_cars(question, record_id):
    reply = ask(question)
    assert reply["answer_type"] == "penalty"
    assert reply["penalty"]["record_id"] == record_id


def test_owner_overload_question_offers_both_owner_frameworks():
    reply = ask("Xe khách chở quá số người quy định bị phạt bao nhiêu?")
    assert reply["answer_type"] == "clarify"
    assert reply["reason"] == "conduct"
    assert {option["record_id"] for option in reply["options"]} == {
        "nd168-d32-k5", "nd168-d32-k6",
    }


@pytest.mark.parametrize(
    "question, vehicle, reason, record_ids",
    [
        (
            "Không đội mũ bảo hiểm phạt bao nhiêu?", "xe_may", "helmet_role",
            {"nd168-d7-k2-h", "nd168-d7-k2-i", "nd168-d12-k5-b"},
        ),
        (
            "Nồng độ cồn phạt bao nhiêu?", "xe_may", "alcohol_level",
            {"nd168-d7-k6-a", "nd168-d7-k8-b", "nd168-d7-k9-d", "nd168-d7-k9-đ"},
        ),
        (
            "Chạy quá tốc độ phạt bao nhiêu?", "o_to", "speed_excess",
            {"nd168-d6-k3-a", "nd168-d6-k5-đ", "nd168-d6-k6-a", "nd168-d6-k7-a"},
        ),
        (
            "Không có bằng lái phạt bao nhiêu?", "xe_may", "engine_size",
            {"nd168-d18-k5-a", "nd168-d18-k7-b"},
        ),
        (
            "Không thắt dây an toàn phạt bao nhiêu?", "o_to", "seatbelt_role",
            {"nd168-d6-k3-k", "nd168-d6-k3-l", "nd168-d12-k4"},
        ),
        (
            "Đi ngược chiều phạt bao nhiêu?", "o_to", "road_type",
            {"nd168-d6-k9-d", "nd168-d6-k11-đ"},
        ),
        (
            "Gây tai nạn giao thông phạt bao nhiêu?", "xe_may", "accident_cause",
            {"nd168-d7-k10-b", "nd168-d7-k10-a"},
        ),
    ],
)
def test_common_clarifications_offer_clickable_penalties(question, vehicle, reason, record_ids):
    reply = ask(question, vehicle)
    assert reply["answer_type"] == "clarify"
    assert reply["reason"] == reason
    assert {option["record_id"] for option in reply["options"]} == record_ids
    for option in reply["options"]:
        chosen = call("POST", "/chat", {"question": "chọn phương án", "record_id": option["record_id"]}).json()
        assert chosen["answer_type"] == "penalty"
        assert chosen["penalty"]["record_id"] == option["record_id"]
        assert chosen["sources"]


def test_phone_and_motorbike_wrong_way_questions_answer_without_a_dead_end():
    assert ask("Sử dụng điện thoại khi lái xe phạt bao nhiêu?", "xe_may")["penalty"]["record_id"] == "nd168-d7-k4-đ"
    assert ask("Sử dụng điện thoại khi lái xe phạt bao nhiêu?", "o_to")["penalty"]["record_id"] == "nd168-d6-k5-h"
    assert ask("Xe máy đi ngược chiều phạt bao nhiêu?")["penalty"]["record_id"] == "nd168-d7-k7-a"


def test_followup_vehicle_and_validation():
    assert ask("Vượt đèn đỏ phạt bao nhiêu?", "xe_may")["answer_type"] == "penalty"
    assert call("POST", "/chat", {"question": " \t "}).status_code == 422
    assert call("POST", "/chat", {"question": "Vượt đèn đỏ?", "vehicle_type": "xe_tai"}).status_code == 422


def test_missing_catalog_returns_503_without_creating_a_file():
    with TemporaryDirectory() as directory:
        db = Path(directory) / "missing.db"
        application = create_app(db)
        assert call("GET", "/health", application=application).status_code == 503
        assert call("POST", "/chat", {"question": "Xe máy vượt đèn đỏ"}, application).status_code == 503
        assert not db.exists()


@pytest.mark.parametrize(
    "question, record_id",
    [
        ("Ô tô chở khách chở quá số người quy định bị phạt bao nhiêu?", "nd168-d32-k5"),
        ("Xe ô tô khách tuyến cố định chạy trên 300 km chở quá số người bị phạt bao nhiêu?", "nd168-d32-k6"),
        ("Chủ xe ô tô đầu kéo không lắp thiết bị giám sát hành trình bị phạt bao nhiêu?", "nd168-d32-k9a-a"),
        ("Chủ xe ô tô cho nhân viên chở khách thu tiền bị phạt bao nhiêu?", "nd168-d32-k11-e"),
        ("Chủ xe ô tô giao xe chở container bị cắt nóc bị phạt bao nhiêu?", "nd168-d32-k13-e"),
    ],
)
def test_new_article_32_routes(question, record_id):
    reply = ask(question)
    assert reply["answer_type"] == "penalty"
    assert reply["penalty"]["record_id"] == record_id
