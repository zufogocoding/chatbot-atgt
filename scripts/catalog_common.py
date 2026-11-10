#!/usr/bin/env python3
"""Shared helpers for catalog build and lookup scripts."""
from __future__ import annotations

import json
import re
import unicodedata
from pathlib import Path
from typing import Any


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def strip_accents(text: str) -> str:
    text = unicodedata.normalize("NFD", text)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return text.replace("đ", "d").replace("Đ", "D")


def normalize_text(text: str) -> str:
    """Lowercase, accent-free, punctuation-free text for matching.

    "Vượt đèn đỏ!" -> "vuot den do"
    """
    text = strip_accents(text).lower()
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokens(text: str) -> list[str]:
    return [t for t in normalize_text(text).split() if t]


def format_money(value: int | None) -> str:
    if value is None:
        return "—"
    return f"{value:,}".replace(",", ".") + " đồng"


def format_range(fine_min: int | None, fine_max: int | None) -> str:
    if fine_min is None and fine_max is None:
        return "không phạt tiền"
    if fine_min == 0 and fine_max == 0:
        return "cảnh cáo (0 đồng)"
    if fine_min == fine_max:
        return format_money(fine_min)
    return f"{format_money(fine_min)} – {format_money(fine_max)}"


def format_penalty(penalty: dict[str, Any]) -> str:
    kind = penalty.get("type")
    condition = penalty.get("condition")
    condition_text = ""
    if condition:
        condition_text = condition[0].lower() + condition[1:]
    if kind == "tuoc_gplx":
        text = "Tước quyền sử dụng GPLX {}–{} tháng".format(
            penalty.get("min_months"), penalty.get("max_months")
        )
    elif kind == "tich_thu_phuong_tien":
        text = "Bị tịch thu phương tiện"
        if condition_text:
            return f"Bị tịch thu phương tiện nếu {condition_text}"
    elif kind == "tich_thu_thiet_bi":
        text = "Tịch thu thiết bị"
    elif kind == "tich_thu_bien_so":
        text = "Tịch thu biển số"
    elif kind == "tuoc_giay_kiem_dinh":
        text = "Tước quyền sử dụng chứng nhận kiểm định và tem kiểm định {}–{} tháng".format(
            penalty.get("min_months"), penalty.get("max_months")
        )
    elif kind == "tuoc_phu_hieu":
        text = "Tước quyền sử dụng phù hiệu {}–{} tháng".format(
            penalty.get("min_months"), penalty.get("max_months")
        )
    elif kind == "thu_hoi_gplx":
        text = "Thu hồi giấy phép lái xe"
        if condition_text:
            return f"Thu hồi GPLX nếu {condition_text}"
    elif kind == "thu_hoi_dang_ky_xe":
        text = "Thu hồi chứng nhận đăng ký xe"
        if penalty.get("description"):
            text = f"Thu hồi {penalty['description']}"
    elif kind == "thu_hoi_ho_so":
        text = "Thu hồi hồ sơ/giấy tờ không hợp lệ"
        if penalty.get("description"):
            text = f"Thu hồi {penalty['description']}"
    elif kind == "bien_phap_khac_phuc":
        text = "Buộc khắc phục hậu quả"
        if penalty.get("description"):
            desc = penalty["description"]
            text = f"Buộc {desc[0].lower() + desc[1:]}"
    else:
        text = str(kind)
    if condition_text:
        text += f" (điều kiện: {condition_text})"
    return text


def legal_path(rec: dict[str, Any]) -> str:
    basis = rec.get("legal_basis")
    if basis:
        article, clause, point = basis["article"], basis["clause"], basis.get("point")
    else:
        article, clause, point = rec["article"], rec["clause"], rec.get("point")
    path = f"Điều {article} khoản {clause}"
    if point:
        path += f" điểm {point}"
    return path
