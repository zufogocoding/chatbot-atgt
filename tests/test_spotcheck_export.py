from scripts.export_spotcheck import VIOLATIONS, load_jsonl, risk_reasons, select_records


def fine_records():
    return [rec for rec in load_jsonl(VIOLATIONS) if rec["record_kind"] == "fine"]


def test_spotcheck_is_deterministic_and_covers_risk_groups():
    records = fine_records()
    first = select_records(records, 30)
    second = select_records(records, 30)

    assert [rec["id"] for rec in first] == [rec["id"] for rec in second]
    assert len(first) == 30
    assert len({rec["id"] for rec in first}) == 30
    assert all(rec["record_kind"] == "fine" for rec in first)

    # Every sampled record must explain why it is high risk.
    assert all(risk_reasons(rec) for rec in first)
    # All four passenger records are small enough to include in full.
    assert sum(rec["subject"] == "nguoi_duoc_cho" for rec in first) == 4


def test_spotcheck_respects_a_smaller_limit():
    selected = select_records(fine_records(), 5)
    assert len(selected) == 5
    assert len({rec["id"] for rec in selected}) == 5
