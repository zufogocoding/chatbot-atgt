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
        "org_fine_ok": "NA",
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


def test_merge_rejects_modified_catalog_text(tmp_path: Path):
    records = catalog()
    records[0]["behavior_text"] = "Hành vi gốc"
    review_a = reviews("An")
    review_a["fine-1"]["behavior_text"] = "Hành vi bị sửa"
    _, errors, _, _ = merge(
        records, review_a, reviews("Binh"), tmp_path / "a.csv", tmp_path / "b.csv"
    )
    assert any("catalog column behavior_text was modified" in error for error in errors)


def test_merge_accepts_untouched_catalog_columns(tmp_path: Path):
    records = catalog()
    records[0]["behavior_text"] = "Hành vi gốc"
    review_a = reviews("An")
    review_a["fine-1"]["behavior_text"] = "Hành vi gốc"
    _, errors, _, _ = merge(
        records, review_a, reviews("Binh"), tmp_path / "a.csv", tmp_path / "b.csv"
    )
    assert errors == []


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


def per_person_catalog() -> list[dict]:
    rec = record("per-person-1", 800_000, 1_200_000, "fine")
    rec.update({
        "fine_unit": "per_person",
        "fine_cap": 75_000_000,
        "fine_by_subject": {
            "to_chuc": {"min": 1_600_000, "max": 2_400_000, "cap": 150_000_000}
        },
    })
    return [rec]


def per_person_row(rid: str, reviewer: str, **overrides: str) -> dict[str, str]:
    values = {
        "id": rid,
        "expected_fine_min": "800000",
        "expected_fine_max": "1200000",
        "expected_fine_cap": "75000000",
        "expected_fine_org_min": "1600000",
        "expected_fine_org_max": "2400000",
        "expected_fine_org_cap": "150000000",
        "fine_ok": "OK",
        "org_fine_ok": "OK",
        "citation_ok": "OK",
        "text_ok": "OK",
        "reviewer": reviewer,
        "reviewed_at": "2026-11-10",
    }
    values.update(overrides)
    return values


def test_merge_accepts_per_person_caps_and_org_fine(tmp_path: Path):
    verified, errors, _, _ = merge(
        per_person_catalog(),
        {"per-person-1": per_person_row("per-person-1", "An")},
        {"per-person-1": per_person_row("per-person-1", "Binh")},
        tmp_path / "a.csv", tmp_path / "b.csv",
    )
    assert errors == []
    assert verified[0]["verification"]["status"] == "verified"


def test_merge_rejects_missing_per_person_cap(tmp_path: Path):
    _, errors, _, _ = merge(
        per_person_catalog(),
        {"per-person-1": per_person_row("per-person-1", "An", expected_fine_cap="")},
        {"per-person-1": per_person_row("per-person-1", "Binh")},
        tmp_path / "a.csv", tmp_path / "b.csv",
    )
    assert any("missing expected_fine_cap" in error for error in errors)


def test_merge_rejects_wrong_org_cap(tmp_path: Path):
    _, errors, _, _ = merge(
        per_person_catalog(),
        {"per-person-1": per_person_row("per-person-1", "An", expected_fine_org_cap="140000000")},
        {"per-person-1": per_person_row("per-person-1", "Binh")},
        tmp_path / "a.csv", tmp_path / "b.csv",
    )
    assert any("expected_fine_org_cap=140000000" in error for error in errors)


def test_merge_requires_org_check_when_org_fine_exists(tmp_path: Path):
    _, errors, _, _ = merge(
        per_person_catalog(),
        {"per-person-1": per_person_row("per-person-1", "An", org_fine_ok="NA")},
        {"per-person-1": per_person_row("per-person-1", "Binh")},
        tmp_path / "a.csv", tmp_path / "b.csv",
    )
    assert any("org_fine_ok must be OK" in error for error in errors)
