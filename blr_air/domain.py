from dataclasses import dataclass
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

Activity = Literal["run", "cycle", "walk", "commute", "kids"]
Day = Literal["next48", "today", "tomorrow"]
Period = Literal["any", "morning", "afternoon", "evening"]
PlaceName = Annotated[str, Field(min_length=2, max_length=160)]


class AirError(Exception):
    """An actionable error that can be shown in a chat or CLI."""


class ProviderError(AirError):
    pass


class LocationError(AirError):
    pass


class NoWindowError(AirError):
    pass


class RequestSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    place: str = Field(default="Bengaluru", min_length=2, max_length=160)
    activity: Activity = "walk"
    hours: int = Field(default=1, ge=1, le=2, strict=True)
    day: Day = "next48"
    period: Period = "any"
    places: list[PlaceName] = Field(default_factory=list, max_length=3)
    max_aqi: float | None = Field(default=None, ge=0, le=500, allow_inf_nan=False)
    max_rain: float | None = Field(default=None, ge=0, le=100, allow_inf_nan=False)
    max_temperature: float | None = Field(default=None, ge=-80, le=70, allow_inf_nan=False)
    max_uv: float | None = Field(default=None, ge=0, le=30, allow_inf_nan=False)
    max_wind: float | None = Field(default=None, ge=0, le=200, allow_inf_nan=False)
    daylight_only: bool = Field(default=False, strict=True)
    include_venue: bool = Field(default=False, strict=True)

    @field_validator("places")
    @classmethod
    def distinct_places(cls, places):
        if len({place.casefold() for place in places}) != len(places):
            raise ValueError("Comparison places must be distinct.")
        return places


@dataclass(frozen=True)
class Location:
    name: str
    latitude: float
    longitude: float
    timezone: str | None = None


@dataclass(frozen=True)
class Hour:
    time: datetime
    us_aqi: float
    pm2_5: float
    rain_probability: float
    temperature: float
    apparent_temperature: float | None = None
    uv_index: float | None = None
    wind_speed: float | None = None


@dataclass(frozen=True)
class CurrentAir:
    time: datetime
    us_aqi: float
    pm2_5: float


@dataclass(frozen=True)
class Forecast:
    hours: tuple[Hour, ...]
    current: CurrentAir | None
    timezone: str
    fetched_at: datetime
    is_demo: bool = False
    daylight: tuple[tuple[datetime, datetime], ...] = ()


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime
    us_aqi: float
    pm2_5: float
    rain_probability: float
    temperature: float
    max_aqi: float
    score: float
    apparent_temperature: float | None = None
    uv_index: float | None = None
    wind_speed: float | None = None
    daylight: bool | None = None
