import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from catalog_common import format_penalty  # noqa: E402


def record(rid: str) -> dict:
    with (ROOT / "data/catalog/consolidated/violations.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            item = json.loads(line)
            if item["id"] == rid:
                return item
    raise AssertionError(f"missing catalog record {rid}")


def penalties(rid: str, field: str) -> list[dict]:
    return record(rid)[field]


def test_condition_on_inspection_suspension():
    items = penalties("nd168-d32-k7-e", "additional_penalties")
    assert len(items) == 1
    assert items[0]["type"] == "tuoc_giay_kiem_dinh"
    assert "thùng xe" in items[0]["condition"]
    formatted = format_penalty(items[0])
    assert formatted.startswith("Tước quyền sử dụng chứng nhận kiểm định")
    assert "giấy chứng nhận" not in formatted
    # 238/2026 removed "điểm e, điểm g khoản 7" from 32.18.đ.
    assert not any(item["type"] == "tuoc_phu_hieu" for item in items)


def test_phu_hieu_condition_and_missing_penalty_after_238():
    items = penalties("nd168-d32-k11-b", "additional_penalties")
    by_type = {item["type"]: item for item in items}
    assert "thùng xe" in by_type["tuoc_giay_kiem_dinh"]["condition"]
    assert by_type["tuoc_phu_hieu"]["condition"] == "có phù hiệu"
    assert penalties("nd168-d32-k7-g", "additional_penalties") == []


def test_remedial_measure_conditions():
    items = penalties("nd168-d32-k7-g", "remedial_measures")
    assert len(items) == 1
    assert items[0]["condition"] == "gây hư hại cầu, đường"
    assert format_penalty(items[0]).startswith("Buộc khôi phục lại tình trạng ban đầu")
    assert "gây hư hại cầu, đường" in format_penalty(items[0])

    items = penalties("nd168-d32-k11-b", "remedial_measures")
    assert len(items) == 2
    conditions = {item["condition"] for item in items}
    assert conditions == {
        "gây hư hại cầu, đường",
        "phương tiện có thùng xe, khối lượng hàng hóa cho phép chuyên chở không đúng theo quy định hiện hành",
    }


def test_238_replaces_giay_in_clause_19_and_20():
    remedial = format_penalty(penalties("nd168-d32-k7-b", "remedial_measures")[0])
    assert "chứng nhận kiểm định an toàn kỹ thuật" in remedial
    assert "giấy chứng nhận kiểm định an toàn kỹ thuật" not in remedial

    remedial = format_penalty(penalties("nd168-d32-k8-a", "remedial_measures")[0])
    assert "chứng nhận đăng ký xe, chứng nhận kiểm định an toàn kỹ thuật" in remedial
    assert "chứng nhận đăng ký xe, giấy chứng nhận kiểm định" not in remedial


def test_confiscation_condition_keeps_all_alternative_branches():
    for rid in ("nd168-d13-k4-a", "nd168-d14-k2-a", "nd168-d32-k8-e"):
        item = next(
            penalty
            for penalty in penalties(rid, "additional_penalties")
            if penalty["type"] == "tich_thu_phuong_tien"
        )
        condition = item["condition"]
        assert "không có chứng nhận đăng ký xe" in condition
        assert "không do cơ quan có thẩm quyền cấp" in condition
        assert "không đúng số khung" in condition
        assert "bị tẩy xóa" in condition
        assert "không chứng minh được nguồn gốc" in condition
        if rid == "nd168-d32-k8-e":
            assert "có chứng nhận đăng ký xe nhưng" in condition

        formatted = format_penalty(item)
        assert formatted.startswith("Bị tịch thu phương tiện nếu")
        assert "Có thể" not in formatted


def test_revocation_description_comes_from_rule_text():
    items = [
        measure
        for measure in penalties("nd168-d13-k6-a", "remedial_measures")
        if measure["type"] == "thu_hoi_dang_ky_xe"
    ]
    assert len(items) == 1
    description = items[0]["description"]
    assert description.startswith("chứng nhận đăng ký xe")
    assert "không đúng số khung" in description
    assert "không do cơ quan có thẩm quyền cấp" in description
    assert "giấy chứng nhận, tem kiểm định" in description

    formatted = format_penalty(items[0])
    assert formatted.startswith("Thu hồi chứng nhận đăng ký xe")
    assert "giấy chứng nhận, tem kiểm định" in formatted

    items = [
        measure
        for measure in penalties("nd168-d14-k2-b", "remedial_measures")
        if measure["type"] == "thu_hoi_dang_ky_xe"
    ]
    assert len(items) == 1
    description = items[0]["description"]
    assert description.startswith("chứng nhận đăng ký xe")
    assert "không đúng số khung" in description
    assert "không do cơ quan có thẩm quyền cấp" in description
    assert "giấy chứng nhận, tem kiểm định" not in description
