from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


Status = Literal["quiet", "disturbed", "motion", "occupied"]
EventLabel = Literal["unknown", "human", "pet", "hvac", "false_positive"]


def utc_now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class IncomingSample(BaseModel):
    timestamp: str | None = None
    source: str = "manual"
    channel: int | None = None
    frequency_mhz: int | None = None
    bssid: str | None = None
    client_mac: str | None = None
    rssi: float | None = None
    bfi_variance: float = Field(ge=0)
    amplitude_delta: float | None = None
    phase_delta: float | None = None
    motion_score: float | None = Field(default=None, ge=0, le=1)
    raw_json: dict[str, Any] | None = None


class ProcessedSample(IncomingSample):
    timestamp: str
    motion_score: float = Field(ge=0, le=1)
    status: Status
    baseline_delta: float | None = None


class SettingsUpdate(BaseModel):
    settings: dict[str, str | int | float | bool]


class BaselineRequest(BaseModel):
    duration_seconds: int = Field(default=300, gt=0)
    notes: str | None = None


class EventLabelRequest(BaseModel):
    label: EventLabel
    notes: str | None = None
