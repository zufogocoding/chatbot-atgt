import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from merge_reviews import merge  # noqa: E402


def record(rid: str, fine_min, fine_max, kind: str) -> dict:
    return {
        "id": rid,
        "fine_min": fine_min,
        "fine_max": fine_max,
        "record_kind": kind,
        "verification": {"status": "draft", "notes": "test"},
        "version": {"consolidated_as_of": "2026-11-09"},
    }


def row(rid: str, reviewer: str, fine_min="", fine_max="", fine_ok="NA") -> dict:
    return {
        "id": rid,
        "expected_fine_min": fine_min,
        "expected_fine_max": fine_max,
        "fine_ok": fine_ok,
        "citation_ok": "OK",
        "text_ok": "OK",
        "reviewer": reviewer,
        "reviewed_at": "2026-11-10",
    }


def catalog():
    return [
        record("fine-1", 100_000, 200_000, "fine"),
        record("other-1", None, None, "confiscation"),
    ]


def reviews(reviewer: str) -> dict[str, dict[str, str]]:
    return {
        "fine-1": row("fine-1", reviewer, "100000", "200000", "OK"),
        "other-1": row("other-1", reviewer),
    }


def test_merge_marks_verified_when_both_reviews_agree(tmp_path: Path):
    verified, errors, names, verified_at = merge(
        catalog(), reviews("An"), reviews("Binh"), tmp_path / "a.csv", tmp_path / "b.csv"
    )
    assert errors == []
    assert len(verified) == 2
    assert {r["verification"]["status"] for r in verified} == {"verified"}
    assert names == ["An + Binh"]
    assert verified_at == "2026-11-10"
    assert verified[0]["verification"]["notes"] == "test"


def test_merge_rejects_a_failed_check(tmp_path: Path):
    review_b = reviews("Binh")
    review_b["fine-1"]["fine_ok"] = "SAI"
    verified, errors, _, _ = merge(
        catalog(), reviews("An"), review_b, tmp_path / "a.csv", tmp_path / "b.csv"
    )
    assert verified == []
    assert any("fine_ok is SAI" in error for error in errors)


def test_merge_rejects_wrong_amount(tmp_path: Path):
    review_b = reviews("Binh")
    review_b["fine-1"]["expected_fine_max"] = "300000"
    _, errors, _, _ = merge(
        catalog(), reviews("An"), review_b, tmp_path / "a.csv", tmp_path / "b.csv"
    )
    assert any("expected_fine_max=300000" in error for error in errors)


def test_merge_rejects_same_reviewer(tmp_path: Path):
    _, errors, _, _ = merge(
        catalog(), reviews("An"), reviews("an"), tmp_path / "a.csv", tmp_path / "b.csv"
    )
    assert any("must be different people" in error for error in errors)


def test_merge_rejects_missing_record(tmp_path: Path):
    partial = reviews("Binh")
    del partial["other-1"]
    _, errors, _, _ = merge(
        catalog(), reviews("An"), partial, tmp_path / "a.csv", tmp_path / "b.csv"
    )
    assert any("missing 1 records" in error for error in errors)


def test_fine_only_keeps_other_records_draft(tmp_path: Path):
    fine_reviews = {"fine-1": row("fine-1", "An", "100000", "200000", "OK")}
    review_b = {"fine-1": row("fine-1", "Binh", "100000", "200000", "OK")}
    verified, errors, names, _ = merge(
        catalog(), fine_reviews, review_b, tmp_path / "a.csv", tmp_path / "b.csv", fine_only=True
    )
    assert errors == []
    assert names == ["An + Binh"]
    by_id = {record["id"]: record for record in verified}
    assert by_id["fine-1"]["verification"]["status"] == "verified"
    assert by_id["other-1"]["verification"]["status"] == "draft"
