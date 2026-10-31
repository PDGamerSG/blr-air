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


def select_windows(
    rows, request: RequestSpec, timezone: str, now, *, limit=1, daylight=()
) -> list[Window]:
    if type(limit) is not int or not 1 <= limit <= 3:
        raise ValueError("Choose between one and three windows.")
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
        if request.daylight_only and not any(
            rise <= block[0].time and end <= setting for rise, setting in daylight
        ):
            continue
        constraints = (
            ("us_aqi", request.max_aqi),
            ("rain_probability", request.max_rain),
            ("apparent_temperature", request.max_temperature),
            ("uv_index", request.max_uv),
            ("wind_speed", request.max_wind),
        )
        if any(
            limit_value is not None
            and any(
                getattr(row, field) is None or getattr(row, field) > limit_value for row in block
            )
            for field, limit_value in constraints
        ):
            continue
        candidates.append((mean(hourly_cost(row) for row in block), block[0].time, block))
    if not candidates:
        raise NoWindowError(
            "No complete outdoor window matches this request in the next 48 hours. "
            "Try 1 hour, another part of the day, or explicitly adjust your limits. "
            "Missing data cannot satisfy a limit; limits are never relaxed automatically."
        )
    ranked = sorted(candidates, key=lambda candidate: candidate[:2])
    selected = []
    for score, _, block in ranked:
        start, end = block[0].time, block[-1].time + timedelta(hours=1)
        if any(
            start < existing_end and end > existing_start
            for existing_start, existing_end, _, _ in selected
        ):
            continue
        selected.append((start, end, block, score))
        if len(selected) >= limit:
            break
    return [
        Window(
            start=block[0].time.astimezone(tz),
            end=(block[-1].time + timedelta(hours=1)).astimezone(tz),
            us_aqi=mean(row.us_aqi for row in block),
            pm2_5=mean(row.pm2_5 for row in block),
            rain_probability=max(row.rain_probability for row in block),
            temperature=max(row.temperature for row in block),
            max_aqi=max(row.us_aqi for row in block),
            score=score,
            apparent_temperature=complete_peak(block, "apparent_temperature"),
            uv_index=complete_peak(block, "uv_index"),
            wind_speed=complete_peak(block, "wind_speed"),
            daylight=any(rise <= start and end <= setting for rise, setting in daylight)
            if daylight
            else None,
        )
        for start, end, block, score in selected
    ]


def complete_peak(block, field):
    values = [getattr(row, field) for row in block]
    return max(values) if all(value is not None for value in values) else None


def select_window(rows, request: RequestSpec, timezone: str, now, *, daylight=()) -> Window:
    return select_windows(rows, request, timezone, now, limit=1, daylight=daylight)[0]
