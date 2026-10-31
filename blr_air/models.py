from typing import Literal

from pydantic.v1 import Field, confloat, conint
from uagents import Model


class WindowRequest(Model):
    latitude: confloat(ge=-90, le=90, allow_inf_nan=False)
    longitude: confloat(ge=-180, le=180, allow_inf_nan=False)
    hours: conint(strict=True, ge=1, le=2) = 1
    activity: Literal["run", "cycle", "walk", "commute", "kids"] = "walk"
    day: Literal["next48", "today", "tomorrow"] = "next48"
    period: Literal["any", "morning", "afternoon", "evening"] = "any"


class WindowResponse(Model):
    status: Literal["ok", "error"]
    summary: str
    start: str | None = None
    end: str | None = None
    timezone: str | None = None
    us_aqi: float | None = None
    pm2_5: float | None = None
    rain_probability: float | None = None
    temperature: float | None = None
    max_aqi: float | None = None
    fetched_at: str | None = None
    source: str | None = None
    error_code: str | None = None


class HealthResponse(Model):
    status: str = "ok"
    address: str
    mode: str
    version: str = "0.1.0"


class UsageResponse(Model):
    queries: int = Field(ge=0)
    successful_queries: int = Field(ge=0)
    failed_queries: int = Field(ge=0)
    unique_senders: int = Field(ge=0)
    chat_queries: int = Field(ge=0)
    typed_queries: int = Field(ge=0)
