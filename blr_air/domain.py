from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Activity = Literal["run", "cycle", "walk", "commute", "kids"]
Day = Literal["next48", "today", "tomorrow"]
Period = Literal["any", "morning", "afternoon", "evening"]


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
