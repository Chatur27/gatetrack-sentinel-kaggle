from __future__ import annotations

from datetime import date, time

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .enums import RequestedArea, VisitorType


class VisitorRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    visitor_name: str = Field(min_length=2, max_length=100)
    visitor_type: VisitorType
    host_name: str | None = Field(default=None, max_length=100)
    host_confirmed: bool = False
    organisation: str | None = Field(default=None, max_length=150)
    visit_purpose: str | None = Field(default=None, max_length=300)
    visit_date: date
    arrival_time: time
    expected_duration_minutes: int = Field(default=60, ge=1, le=1440)
    requested_area: RequestedArea
    identity_document_type: str | None = Field(default=None, max_length=50)
    visits_last_30_days: int = Field(default=0, ge=0, le=100)
    additional_notes: str = Field(default="", max_length=1000)

    @field_validator("visitor_name", "host_name", "organisation", "visit_purpose")
    @classmethod
    def normalise_spacing(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return " ".join(value.split())
