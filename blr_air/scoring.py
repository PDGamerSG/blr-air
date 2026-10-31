from datetime import time, timedelta
from statistics import mean
from zoneinfo import ZoneInfo

from blr_air.domain import Hour, NoWindowError, RequestSpec, Window


def aqi_category(aqi: float) -> str:
    for ceiling, name in (
        (50, "Good"),
        (100, "Moderate"),
        (150, "Unhealthy for sensitive groups"),
        (200, "Unhealthy"),
        (300, "Very unhealthy"),
    ):
        if aqi <= ceiling:
            return name
    return "Hazardous"


def hourly_cost(row: Hour) -> float:
    # A preference heuristic, not a health/exposure model. Lower is better.
    return (
        row.us_aqi + 0.5 * row.pm2_5 + 1.5 * row.rain_probability + 5 * max(0, row.temperature - 30)
    )


def select_window(rows, request: RequestSpec, timezone: str, now) -> Window:
    tz = ZoneInfo(timezone)
    today = now.astimezone(tz).date()
    target_day = {"today": today, "tomorrow": today + timedelta(days=1)}.get(request.day)
    start_hour, end_hour = {
        "any": (5, 21),
        "morning": (5, 12),
        "afternoon": (12, 17),
        "evening": (17, 21),
    }[request.period]
    # UTC timestamps preserve elapsed hours even on daylight-saving transitions.
    ordered = sorted({row.time: row for row in rows}.values(), key=lambda row: row.time)
    candidates = []
    for i in range(len(ordered) - request.hours + 1):
        block = ordered[i : i + request.hours]
        end = block[-1].time + timedelta(hours=1)
        if block[0].time < now or end > now + timedelta(hours=48):
            continue
        if any(
            b.time - a.time != timedelta(hours=1) for a, b in zip(block, block[1:], strict=False)
        ):
            continue
        local = [row.time.astimezone(tz) for row in block]
        if any(not start_hour <= t.hour < end_hour for t in local):
            continue
        local_end = end.astimezone(tz)
        if local_end.date() != local[0].date() or local_end.time() > time(end_hour):
            continue
        if target_day and any(t.date() != target_day for t in local):
            continue
        candidates.append((mean(hourly_cost(row) for row in block), block[0].time, block))
    if not candidates:
        raise NoWindowError(
            "No complete outdoor window matches this request in the next 48 hours. "
            "Try 1 hour, another part of the day, or try again when forecasts update."
        )
    score, _, block = min(candidates, key=lambda candidate: candidate[:2])
    return Window(
        start=block[0].time.astimezone(tz),
        end=(block[-1].time + timedelta(hours=1)).astimezone(tz),
        us_aqi=mean(row.us_aqi for row in block),
        pm2_5=mean(row.pm2_5 for row in block),
        rain_probability=max(row.rain_probability for row in block),
        temperature=max(row.temperature for row in block),
        max_aqi=max(row.us_aqi for row in block),
        score=score,
    )
