"""HTTP contracts for the traffic lookup API."""
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Vehicle = Literal["xe_may", "o_to"]
Intent = Literal["penalty_lookup", "procedure", "other"]
AnswerType = Literal["penalty", "procedure", "clarify", "refuse"]


class ChatRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    question: str = Field(min_length=1, max_length=1000)
    vehicle_type: Vehicle | None = None
    # Set when the client selects a clarification option. The record is
    # authoritative, so no further intent parsing is needed.
    record_id: str | None = Field(default=None, max_length=64)


class Source(BaseModel):
    document: str
    locator: str
    url: str
    pages: list[int] = Field(default_factory=list)


class Fine(BaseModel):
    min: int | None
    max: int | None


class Penalty(BaseModel):
    record_id: str
    vehicle_type: Literal["xe_may", "o_to", "both"]
    subject: str
    record_kind: str
    behavior: str
    legal_path: str
    fine: Fine
    organization_fine: Fine | None = None
    license_points: int
    license_points_condition: str | None = None
    additional_penalties: list[str]
    remedial_measures: list[str]
    verification_status: str
    source_quote: str


class Choice(BaseModel):
    record_id: str
    label: str


class ChatResponse(BaseModel):
    intent: Intent
    answer_type: AnswerType
    answer: str
    as_of: str
    disclaimer: str = "Thông tin tham khảo, không thay thế tư vấn pháp lý."
    reason: str | None = None
    penalty: Penalty | None = None
    options: list[Choice] = Field(default_factory=list)
    related: list[Choice] = Field(default_factory=list)
    sources: list[Source] = Field(default_factory=list)
    procedure_ids: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: Literal["ok"] = "ok"
    as_of: str
    violations: int
    procedures: int
