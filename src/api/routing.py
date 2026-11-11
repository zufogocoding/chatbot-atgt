"""Deterministic intent and qualifier handling for the catalog snapshot."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
import re

from scripts.catalog_common import normalize_text, strip_accents
from scripts.query_catalog import BIKE_RE, CAR_RE, COMMERCIAL_RE

from .schemas import Vehicle

SHORT_FORMS = {
    "k": "khong", "ko": "khong", "dt": "dien thoai", "bn": "bao nhieu",
    "nhiu": "nhieu", "fai": "phai", "yc": "yeu cau", "bh": "bao hiem",
}
SHORT_FORM_RE = re.compile(r"\b(" + "|".join(SHORT_FORMS) + r")\b")
OUTSIDE_VEHICLE = (
    r"\b(?:xe buyt|xe dap(?: may)?|xe tho so|xe may chuyen dung|nguoi di bo)\b"
)
OUTSIDE_REQUEST = (
    r"\b(?:tra (?:cuu )?phat nguoi|tra cuu theo bien so|(?:thanh toan|nop phat).{0,35}(?:ho toi|giup toi luon)"
    r"|du doan.{0,25}(?:ket qua|thang)|khoi kien.{0,35}(?:viet don|mau don)|cham khai thue|tron ve"
    r"|tranh chap dat dai|khieu nai.{0,30}(?:luong|tieng on|thue))\b"
)
HISTORICAL = r"\b(?:(?:thang|ngay) \d{1,2}(?: \d{1,2})?(?: nam)? \d{4}|nam (?:19|20)\d{2})\b"
PROCEDURE = (
    r"\b(?:khieu nai|(?:nop|dong) (?:tien )?phat|cham nop|bien lai|buu chinh cong ich|sau khi thanh toan"
    r"|xin hoan.{0,20}phat|xin (?:giam|mien).{0,20}phat|tam dinh chi thi hanh|phat oan|phat nham)\b"
)
ACCIDENT = r"\b(?:gay (?:ra )?tai nan|(?:dan den|lam xay ra) tai nan|tong (?:xe|nguoi))\b"
NEGATED_ACCIDENT = r"\b(?:khong|chua) (?:he )?(?:gay (?:ra )?tai nan|(?:dan den|lam xay ra) tai nan|tong (?:xe|nguoi))\b"
RED_LIGHT = (
    r"\b(?:vuot|chay qua|chay) den (?:van )?do\b"
    r"|\bvuot qua khi den van do\b|\bkhong dung (?:khi )?den do\b"
)
SPEED = r"\b(?:qua toc do|vuot (?:toc do|gioi han toc do)|ban toc do|phong nhanh)\b"
EXCESS_SPEED = re.compile(
    r"\b(?:qua (?:toc do(?: (?:cho phep|quy dinh))?|gioi han toc do)"
    r"|vuot (?:toc do(?: cho phep)?|gioi han(?: toc do)?))"
    r"\s+(?:dung\s+)?(\d+(?:[,.]\d+)?)\s*(?:km\s*/\s*h|kmh)\b"
)
# "dong thoi con ..." (đồng thời còn ...) must not be read as "thổi cồn".
ALCOHOL = r"\b(?:(?<!dong )thoi (?:nong do )?con|nong do con|do con|co con|kiem tra con|say xin|uong ruou bia)\b"
ALCOHOL_MEASUREMENT = re.compile(
    r"\b(\d+(?:[,.]\d+)?)\s*mg(?:\s+con)?\s*(?:/|tren)\s*"
    r"(?:(?:1\s*)?(l(?:it)?)(?![a-z])|100\s*(ml)(?![a-z]))"
)
LICENSE = r"\b(?:bang lai|giay phep lai xe|gplx|bang)\b"
ENGINE = re.compile(r"\b(\d+(?:[,.]\d+)?)\s*(cc|cm3|phan khoi|kw)\b")
HEIGHT = re.compile(r"\bcao\s+(\d+(?:[,.]\d+)?)\s*(m|cm)\b")
REGISTRATION = r"\b(?:dang ky xe|ca vet|giay dang ky|chung nhan dang ky)\b"


@dataclass(frozen=True)
class Clarification:
    reason: str
    question: str


def normalize_question(question: str) -> tuple[str, str]:
    surface = SHORT_FORM_RE.sub(lambda match: SHORT_FORMS[match[0]], strip_accents(question).lower())
    return surface, normalize_text(surface)


PASSENGER_CUE = r"\b(?:nguoi ngoi sau|nguoi duoc cho|hanh khach|nguoi di cung)\b"
DRIVER_CUE = r"\b(?:nguoi lai|tai xe|cam lai|dieu khien|toi lai|lai xe|toi cho|cho nguoi|cho ban|cho be|cho tre|cho khach)\b"


def includes(pattern: str, text: str) -> bool:
    return re.search(pattern, text) is not None


def mentioned_vehicles(text: str) -> set[Vehicle]:
    vehicles: set[Vehicle] = set()
    if BIKE_RE.search(text):
        vehicles.add("xe_may")
    if CAR_RE.search(text) or includes(r"\bxe con\b", text) or COMMERCIAL_RE.search(text):
        vehicles.add("o_to")
    return vehicles


def decimal(text: str) -> Decimal:
    return Decimal(text.replace(",", "."))


def motorcycle_class(surface: str) -> int | None:
    tiers = {
        decimal(value) > (11 if unit == "kw" else 125)
        for value, unit in ENGINE.findall(surface)
    }
    return int(tiers.pop()) if len(tiers) == 1 else None


def vehicle_path(vehicle: Vehicle, bike: str, car: str) -> str:
    return bike if vehicle == "xe_may" else car


def speed_path(surface: str, vehicle: Vehicle) -> str | Clarification:
    readings = {decimal(value) for value in EXCESS_SPEED.findall(surface)}
    if len(readings) != 1:
        return Clarification("speed_excess", "Bạn chạy vượt tốc độ cho phép bao nhiêu km/h?")
    excess = readings.pop()
    if excess < 5:
        return ""
    if excess < 10:
        return vehicle_path(vehicle, "7.2.b", "6.3.a")
    if excess <= 20:
        return vehicle_path(vehicle, "7.4.a", "6.5.đ")
    if vehicle == "xe_may":
        return "7.8.a"
    return "6.6.a" if excess <= 35 else "6.7.a"


def alcohol_path(surface: str, text: str, vehicle: Vehicle) -> str | Clarification:
    if includes(r"\b(?:tu choi|khong chap hanh)\b.{0,45}\b(?:thoi|kiem tra|do)\b", text):
        return vehicle_path(vehicle, "7.9.đ", "6.11.b")
    measurements = {
        (decimal(value), bool(liter)) for value, liter, _milliliter in ALCOHOL_MEASUREMENT.findall(surface)
    }
    if len(measurements) != 1:
        if measurements or includes(r"\d", text):
            return Clarification("alcohol_unit", "Bạn cho biết chỉ số đo và đơn vị (mg/l khí thở hoặc mg/100 ml máu)?")
        return Clarification("alcohol_level", "Nồng độ cồn đo được là bao nhiêu và dùng đơn vị nào?")
    value, breath = measurements.pop()
    if value == 0:
        return ""
    first, second = (Decimal("0.25"), Decimal("0.4")) if breath else (50, 80)
    if value <= first:
        return vehicle_path(vehicle, "7.6.a", "6.6.c")
    if value <= second:
        return vehicle_path(vehicle, "7.8.b", "6.9.a")
    return vehicle_path(vehicle, "7.9.d", "6.11.a")


def license_path(surface: str, text: str, vehicle: Vehicle) -> str | Clarification:
    if includes(r"\b(?:quen|khong mang|khong co bang trong nguoi)\b", text):
        return Clarification("license_status", "Bạn chưa được cấp bằng, hay có bằng nhưng không mang theo?")
    expired = includes(r"\b(?:het han|qua han)\b", text)
    if vehicle == "xe_may":
        # 18.5.a chỉ áp dụng cho xe mô tô đến 125 cm³, không phải xe gắn máy
        # (đến 50 cm³), nên phải hỏi lại thay vì gán bừa khung phạt.
        if "xe gan may" in text or any(
            decimal(value) <= (4 if unit == "kw" else 50) for value, unit in ENGINE.findall(surface)
        ):
            return Clarification(
                "motorcycle_class",
                "Xe bạn dùng là xe mô tô (trên 50 cm³) hay xe gắn máy (đến 50 cm³)? "
                "Nếu là xe mô tô, chọn dung tích bên dưới.",
            )
        tier = motorcycle_class(surface)
        if tier is None:
            return Clarification("engine_size", "Xe mô tô có dung tích bao nhiêu cm³, hoặc công suất bao nhiêu kW nếu chạy điện?")
        return ("18.5.a", "18.7.b")[tier]
    if not expired:
        return "18.9.b"
    months = re.search(r"\b(\d+)\s*(thang|nam)\b", text)
    if months:
        return "18.8.a" if int(months[1]) * (12 if months[2] == "nam" else 1) < 12 else "18.9.a"
    return Clarification("license_expiry", "Bằng lái ô tô đã hết hạn dưới một năm hay từ một năm trở lên?")


def accident_path(text: str, vehicle: Vehicle) -> str | Clarification:
    if includes(RED_LIGHT, text):
        return vehicle_path(vehicle, "7.10.b", "6.10.b")
    if includes(r"\bnguoc chieu\b", text) and not includes(r"\bcao toc\b", text):
        return vehicle_path(vehicle, "7.10.a", "6.10.b")
    if includes(SPEED + r"|\b(?:sai lan|khong dung (?:lan|phan) duong)\b", text):
        return vehicle_path(vehicle, "7.10.a", "6.10.a")
    return Clarification("accident_cause", "Bạn mô tả hành vi gây tai nạn để mình xác định đúng điều khoản?")


def child_passenger_path(surface: str, text: str) -> str | Clarification:
    age = re.search(r"\b(\d+) tuoi\b", text)
    height = HEIGHT.search(surface)
    if not age or not height:
        return Clarification("child_age_height", "Bạn cho biết tuổi và chiều cao của trẻ?")
    centimeters = decimal(height[1]) * (100 if height[2] == "m" else 1)
    if int(age[1]) >= 10 or centimeters >= 135:
        return ""
    if includes(r"\b(?:cung hang|ngoi canh|ghe truoc)\b", text):
        if includes(r"\b(?:hai|2) hang ghe\b|\bco hang ghe sau\b", text):
            return "6.3.m"
        return Clarification("seat_rows", "Xe có một hàng ghế hay có thêm hàng ghế phía sau?")
    if includes(r"\bkhong (?:dung|su dung)\b.{0,20}\b(?:ghe|thiet bi) an toan\b", text):
        commercial = re.sub(r"\bkhong kinh doanh\b", "", text)
        if includes(r"\bkinh doanh van tai hanh khach\b", commercial):
            return ""
        if includes(r"\b(?:gia dinh|ca nhan|khong kinh doanh)\b", text):
            return "6.1a"
        return Clarification("vehicle_use", "Xe gia đình hay ô tô kinh doanh vận tải hành khách?")
    return Clarification("child_seat", "Trẻ ngồi ở hàng ghế nào và có dùng thiết bị an toàn phù hợp không?")


# Each value is the legal path for a motorcycle and a car respectively.
DIRECT_PATHS = (
    (r"\b(?:khong|chua) (?:lam thu tuc )?sang ten\b|\bkhong (?:lam thu tuc )?dang ky\b.{0,45}\b(?:doi|thay doi) chu\b|\b(?:doi|thay doi) chu\b.{0,25}\bkhong (?:dang ky|lam thu tuc)\b", "32.3.a", "32.7.h"),
    (r"\b(?:giao (?:xe|o to|oto|mo to)|cho.{0,42}muon xe)\b.{0,48}\b(?:khong du dieu kien|khong co bang|chua co bang|chua du tuoi)\b|\bcho nguoi (?:khong du dieu kien|chua du dieu kien|chua co bang) muon xe\b", "32.10", "32.14.i"),
    (r"\b(?:cam|dung tay cam|dung tay)\b.{0,22}\bdien thoai\b", "7.4.đ", "6.5.h"),
    (r"\b(?:khong co|khong mua|het han) bao hiem\b", "18.2.b", "18.4.c"),
    (r"\b(?:khong co|chua co)\b.{0,18}" + REGISTRATION, "14.2.a", "13.4.a"),
    (r"\b(?:khong gan|khong co|thao het)\b.{0,12}\bbien so\b", "14.3.a", "13.7.b"),
    (r"\b(?:bien so|gan bien)\b.{0,20}\b(?:sai vi tri|khong dung vi tri|bi che)\b|\bche\b.{0,24}\b(?:chu so|bien)\b", "14.3.b", "13.8.b"),
    (r"\bbien so (?:gia|cua xe khac)\b", "14.3.a", "13.8.a"),
    (r"\b(?:re (?:trai|phai)|chuyen huong)\b.{0,35}\b(?:khong|quen)\b.{0,10}\b(?:xi nhan|bao re|giam toc do)\b", "7.3.a", "6.3.c"),
    (r"\b(?:sai lan|khong dung (?:lan|phan) duong|qua dai phan cach co dinh)\b", "7.3.d", "6.5.b"),
    (r"\b(?:lang lach|danh vong|quet chan chong)\b", "7.9.a", "6.12"),
    (r"\b(?:khong co|hong|khong hoat dong|khong bao dam tieu chuan)\b.{0,12}\bphanh\b|\bphanh\b.{0,30}\b(?:khong hoat dong|khong bao dam|hong)\b", "14.1.d", "13.5.b"),
)


def direct_path(surface: str, text: str, vehicle: Vehicle) -> str | Clarification | None:
    if includes(r"\b(?:khong|chua) (?:he )?(?:vuot den do|qua toc do|cam dien thoai)\b", text):
        return ""
    if includes(r"\bdien thoai\b", text):
        if includes(r"\bdang do\b", text):
            return ""
        if includes(r"\b(?:da dung han|dang dung (?:cho|o|tai|yen|han|ma))\b", text):
            return Clarification("vehicle_motion", "Xe đang di chuyển hay đã dừng, đỗ tại thời điểm dùng điện thoại?")
    if includes(ACCIDENT, re.sub(NEGATED_ACCIDENT, "", text)):
        return accident_path(text, vehicle)
    if includes(RED_LIGHT, text):
        return vehicle_path(vehicle, "7.7.c", "6.9.b")
    if includes(SPEED, text) or includes(r"\b\d+(?:[,.]\d+)?\s*km\s*/\s*h\b", surface):
        return speed_path(surface, vehicle)
    if includes(ALCOHOL, text) or ("con" in text.split() and ALCOHOL_MEASUREMENT.search(surface)):
        return alcohol_path(surface, text, vehicle)
    if vehicle == "o_to" and includes(r"\bcho (?:be|tre(?: em)?)\b", text):
        return child_passenger_path(surface, text)
    if includes(r"\b(?:chu xe|chu phuong tien)\b", text) and includes(r"\bbien so\b", text):
        if includes(r"\bdua\b.{0,30}\b(?:khong gan|khong co)\b.{0,12}\bbien so\b", text):
            return vehicle_path(vehicle, "32.8.h", "32.12.b")
        return Clarification("conduct", "Bạn hỏi trách nhiệm của người lái hay hành vi cụ thể của chủ xe đối với biển số?")
    if includes(r"\b(?:qua han|het han|khong co)\b", text) and includes(r"\b(?:dang kiem|tem kiem dinh|chung nhan kiem dinh)\b", text):
        if vehicle != "o_to":
            return ""
        if includes(r"\bkhong co\b", text):
            return "13.6.b"
        period = re.search(r"\b(?:qua han|het han)\s+(?:dang kiem\s+)?(\d+|mot|hai|ba)\s+(ngay|tuan|thang|nam)\b", text)
        if period:
            value = {"mot": 1, "hai": 2, "ba": 3}.get(period[1], period[1])
            if period[2] in {"thang", "nam"} or (period[2] == "ngay" and int(value) >= 31):
                return "13.6.b"
            if (period[2] == "ngay" and int(value) < 28) or (period[2] == "tuan" and int(value) < 4):
                return "13.5.a"
        return Clarification("inspection_expiry", "Đăng kiểm đã hết hạn dưới một tháng hay từ một tháng trở lên?")
    on_highway = includes(r"\bcao toc\b", text) and not includes(r"\b(?:ngoai|khong tren|khong phai) cao toc\b", text)
    lane_violation = includes(r"\bchuyen lan\b", text) and includes(
        r"\b(?:khong|quen)\b.{0,25}\b(?:bao truoc|xi nhan|khoang cach)\b|\bchuyen lan (?:sai|khong dung)\b", text,
    )
    if on_highway:
        if vehicle == "xe_may" and includes(r"\b(?:vao|len)\b.{0,12}\bcao toc\b", text):
            return "7.7.b"
        if vehicle == "o_to":
            if includes(r"\b(?:nguoc chieu|lui|quay dau)\b", text):
                return "6.11.đ"
            if lane_violation:
                return "6.5.g"
            if includes(r"\b(?:dung|do)\b.{0,22}\b(?:sai quy dinh|noi khong|khong dung noi)\b", text):
                return "6.7.c"
    if not on_highway and includes(r"\bnguoc chieu\b", text):
        if includes(r"\b(?:duong mot chieu|bien cam|trong pho)\b", text):
            return vehicle_path(vehicle, "7.7.a", "6.9.d")
        if vehicle == "xe_may":
            # Cùng một khung phạt cho cả đường một chiều và đường khác.
            return "7.7.a"
        return Clarification(
            "road_type",
            "Bạn đi ngược chiều trong đô thị/đường một chiều hay trên đường cao tốc?",
        )
    if lane_violation:
        return vehicle_path(vehicle, "7.1.e", "6.2.a")
    for pattern, bike, car in DIRECT_PATHS:
        if includes(pattern, text):
            return vehicle_path(vehicle, bike, car)
    if includes(LICENSE, text) and includes(r"\b(?:khong co|chua co|quen|khong mang|het han|qua han)\b", text):
        return license_path(surface, text, vehicle)
    if vehicle == "xe_may":
        if includes(PASSENGER_CUE, text) and includes(
            r"\b(?:che|su dung|dung)\b.{0,12}\b(?:o|du)\b", text
        ):
            return "12.2.d"
        if includes(PASSENGER_CUE, text) and includes(
            r"\b(?:bam|keo|day)\b.{0,25}\bxe khac\b|\bdung tren yen\b|\bngoi tren tay lai\b"
            r"|\bmang vac vat cong kenh\b|\bgia deo hang\b",
            text,
        ):
            return "12.5.a"
        if includes(r"\bqua so nguoi\b|\bcho qua so nguoi\b", text):
            return Clarification("passenger_count", "Xe chở 2 người hay từ 3 người trở lên?")
        if includes(r"\b(?:khong doi|khong cai|quen doi|quen cai|doi mu)\b.{0,30}\b(?:mu bao hiem|quai mu|quai)\b", text):
            passenger = includes(PASSENGER_CUE, text)
            driver_responsibility = includes(DRIVER_CUE, text)
            if passenger and not driver_responsibility:
                # Điều 12.5.b fines the passenger, not the person driving.
                return "12.5.b"
            if passenger or includes(r"\b(?:ngoi sau|cho (?:nguoi|ban))\b", text):
                return "7.2.i"
            if includes(r"\b(?:toi lai|lai xe|lai xemay|cam lai|dieu khien|nguoi lai)\b", text):
                return "7.2.h"
            return Clarification("helmet_role", "Người lái hay người ngồi sau không đội mũ hoặc không cài quai đúng cách?")
        if includes(r"\b(?:boc dau|chay.{0,20}bang mot banh)\b", text):
            return "7.11.b"
        if (
            includes(r"\b(?:thieu|mat|khong co|khong co tac dung)\b.{0,25}\bguong(?: chieu hau)?\b", text)
            and not includes(r"\bguong ben phai\b", text)
        ) or includes(r"\bguong ben trai\b.{0,30}\bkhong co tac dung\b", text):
            return "14.1.a"
        if includes(r"\b(?:chua tron 18|1[67] tuoi)\b", text) and includes(r"\bmo to\b", text):
            return "18.4.a"
        if includes(r"\b(?:cho (?:ba|3) nguoi|(?:bon|4) nguoi tren mot xe)\b", text):
            return "7.3.b"
        if includes(r"\bcho (?:hai|2) nguoi lon\b|\bcho (?:hai|2) (?:nguoi|ban)\b.{0,30}\bkhong thuoc (?:dien )?ngoai le\b", text):
            return "7.2.g"
        if includes(r"\btai nghe\b", text) and ("tro thinh" not in text or "khong phai thiet bi tro thinh" in text):
            return "7.4.đ"
        if includes(r"\b(?:bam|su dung) coi\b", text) and "lien tuc" not in text:
            if includes(r"\b(?:nua dem|2[23] gio|0?[0-4] gio)\b", text) and includes(r"\b(?:khu (?:dong )?dan cu|co so kham benh)\b", text):
                return "7.1.i"
    elif includes(r"\b(?:khong|quen)\b.{0,14}\b(?:that|cai) day(?: dai)? an toan\b", text) or (
        includes(r"\b(?:hanh khach|ghe phu|nguoi ngoi)\b", text)
        and includes(r"\b(?:khong (?:that|cai) day|ghe co day.{0,18}khong cai)\b", text)
    ):
        passenger = includes(PASSENGER_CUE, text) or includes(r"\b(?:ghe phu|nguoi ngoi)\b", text)
        driver = includes(DRIVER_CUE, text)
        if passenger and not driver:
            # Điều 12.4 fines the passenger who does not wear a seatbelt.
            return "12.4"
        if passenger:
            return "6.3.l"
        if driver:
            return "6.3.k"
        return Clarification("seatbelt_role", "Bạn hỏi về dây an toàn của người lái hay của người ngồi trên xe?")
    if vehicle == "o_to" and includes(r"\b(?:mo cua|de cua)\b", text) and includes(r"\bkhong (?:bao dam )?an toan\b", text):
        return "6.5.q"
    if includes(r"\b(?:khong|quen)\b.{0,15}\b(?:bat|su dung|mo)\b.{0,10}\bden\b|\btat den\b", text):
        if includes(r"\bham(?: duong bo)?\b", text):
            return vehicle_path(vehicle, "7.3.h", "6.3.n")
        if includes(r"\b(?:ban dem|sang|toi|suong mu|mua|(?:1[89]|2[0-3]|0?[0-5]) gio)\b", text):
            return vehicle_path(vehicle, "7.1.g", "6.3.g")
    return None


# Do not split decimals ("20,5 km/h") or the collision words "va chạm"/"va quẹt".
MULTI_SPLIT = re.compile(r"\bdong thoi\b|\bva\b(?!\s+(?:cham|quet)\b)|[,;](?!\d)")
HELMET = (
    r"\b(?:khong doi|khong cai|quen doi|quen cai|doi mu)\b.{0,30}"
    r"\b(?:mu bao hiem|quai mu|quai)\b"
)


def _part_violation_paths(surface: str, text: str, vehicle: Vehicle) -> list[str]:
    paths: list[str] = []
    if vehicle == "xe_may":
        total_three = includes(r"\btong (?:3|ba)\b", text)
        all_three = includes(r"\bca (?:3|ba) nguoi\b", text)
        helmet = includes(HELMET, text)
        if total_three:
            # "Tống 3" thường được hiểu là tổng cộng 3 người trên xe
            # (tài xế + 2 người), tức khung chở 02 người.
            paths.append("7.2.g")
        if helmet and all_three:
            # Cả 3 người không đội mũ: tài xế (7.2.h) và người được chở (7.2.i).
            paths.extend(["7.2.h", "7.2.i"])
        elif helmet and not includes(PASSENGER_CUE, text) and not includes(DRIVER_CUE, text):
            # Trong câu nhiều hành vi, "không đội mũ" không nói rõ ai thì
            # mặc định là người lái; không tự quy kết thêm cho người được chở.
            paths.append("7.2.h")
    path = direct_path(surface, text, vehicle)
    if isinstance(path, str) and path and path not in paths:
        paths.append(path)
    return paths


def violation_paths(surface: str, text: str, vehicle: Vehicle) -> list[str]:
    """Return every distinct catalog path mentioned in a compound question.

    The detector is deliberately conservative: accident questions stay with
    ``accident_path`` as one aggravated violation, because splitting them would
    count the base behaviour and the accident separately.
    """
    if includes(r"\btai nan\b", text):
        return []
    paths: list[str] = []
    for part in MULTI_SPLIT.split(surface):
        part = part.strip()
        if not part:
            continue
        for path in _part_violation_paths(part, normalize_text(part), vehicle):
            if path not in paths:
                paths.append(path)
    return paths
