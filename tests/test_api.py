import asyncio
from pathlib import Path
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
    assert reply["penalty"]["fine"] == {"min": minimum, "max": maximum}
    assert reply["sources"][0]["url"].startswith("https://")
    assert "[1]" in reply["answer"]


def test_organization_fine():
    reply = ask("Công ty mua ô tô mà chưa sang tên")
    assert reply["penalty"]["organization_fine"] == {"min": 8_000_000, "max": 12_000_000}
    assert reply["answer"].startswith("Mức phạt tổ chức")


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
    ],
)
def test_common_phrasings(question, record_id):
    reply = ask(question)
    assert reply["answer_type"] == "penalty"
    assert reply["penalty"]["record_id"] == record_id


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
        ("Xe tải vượt đèn đỏ", "refuse", "vehicle_out_of_scope"),
        ("Tôi lái ô tô tải vượt đèn đỏ", "refuse", "vehicle_out_of_scope"),
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
