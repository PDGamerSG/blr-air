from typing import Literal

from pydantic.v1 import Field, StrictBool, confloat, conint, constr, validator
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


class PlanRequest(Model):
    places: list[constr(strip_whitespace=True, min_length=2, max_length=160)] = Field(
        min_items=1, max_items=3
    )
    hours: conint(strict=True, ge=1, le=2) = 1
    activity: Literal["run", "cycle", "walk", "commute", "kids"] = "walk"
    day: Literal["next48", "today", "tomorrow"] = "next48"
    period: Literal["any", "morning", "afternoon", "evening"] = "any"
    max_aqi: confloat(ge=0, le=500, allow_inf_nan=False) | None = None
    max_rain: confloat(ge=0, le=100, allow_inf_nan=False) | None = None
    max_temperature: confloat(ge=-80, le=70, allow_inf_nan=False) | None = None
    max_uv: confloat(ge=0, le=30, allow_inf_nan=False) | None = None
    max_wind: confloat(ge=0, le=200, allow_inf_nan=False) | None = None
    daylight_only: StrictBool = False

    @validator("places")
    def distinct_places(cls, places):
        if len({place.casefold() for place in places}) != len(places):
            raise ValueError("Places must be distinct")
        return places


class WindowOption(Model):
    start: str
    end: str
    us_aqi: float
    pm2_5: float
    rain_probability: float
    temperature: float
    max_aqi: float
    score: float
    aqi_category: str
    apparent_temperature: float | None = None
    uv_index: float | None = None
    wind_speed: float | None = None
    daylight: bool | None = None


class PlaceComparison(Model):
    place: str
    status: Literal["ok", "error"]
    summary: str
    rank: int | None = None
    resolved_name: str | None = None
    timezone: str | None = None
    window: WindowOption | None = None
    backups: list[WindowOption] = Field(default_factory=list)
    source: str | None = None
    fetched_at: str | None = None
    error_code: str | None = None


class PlanResponse(Model):
    status: Literal["ok", "error"]
    summary: str
    winner: str | None = None
    partial: bool = False
    tied_places: list[str] = Field(default_factory=list)
    results: list[PlaceComparison] = Field(default_factory=list)
    error_code: str | None = None


# Names retained for callers of the comparison helper during development.
ComparisonRequest = PlanRequest
ComparisonResponse = PlanResponse


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
