"""Export a selected forecast window as a standalone RFC 5545 calendar event."""

from datetime import UTC, datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from blr_air.domain import AirError
from blr_air.service import LIMITATION, SOURCE, Recommendation


def _text(value: str) -> str:
    """Escape iCalendar TEXT without allowing a new property or component."""
    value = value.replace("\r\n", "\n").replace("\r", "\n")
    if any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise AirError("Calendar text contains an unsupported control character.")
    return value.replace("\\", "\\\\").replace("\n", "\\n").replace(";", "\\;").replace(",", "\\,")


def _fold(line: str) -> str:
    """Keep physical lines within 75 UTF-8 octets, including continuation space."""
    parts, current, size = [], "", 0
    for char in line:
        length = len(char.encode("utf-8"))
        if size + length > 75:
            parts.append(current)
            current, size = " ", 1
        current += char
        size += length
    parts.append(current)
    return "\r\n".join(parts)


def _utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise AirError("Calendar dates must include a timezone.")
    return value.astimezone(UTC)


def write_calendar(
    recommendation: Recommendation,
    path: Path,
    *,
    reminder_minutes: int | None = 60,
) -> Path:
    """Create one event, without overwriting a file or connecting to a calendar service."""
    path = Path(path)
    if path.suffix.lower() != ".ics":
        raise AirError("Choose a calendar filename ending in .ics.")
    if reminder_minutes is not None and (
        type(reminder_minutes) is not int or reminder_minutes <= 0
    ):
        raise AirError("Calendar reminder must be a positive number of minutes or None.")

    window, forecast = recommendation.window, recommendation.forecast
    start, end = _utc(window.start), _utc(window.end)
    if end <= start:
        raise AirError("Calendar end must be after its start.")
    fetched = _utc(forecast.fetched_at or datetime.now(UTC))
    activity = recommendation.request.activity
    location = recommendation.location
    identity = (
        f"https://blr-air.local/window/{location.latitude}/{location.longitude}/"
        f"{start.isoformat()}/{end.isoformat()}/{activity}"
    )
    source = "Synthetic offline demo" if forecast.is_demo else SOURCE
    description = [
        f"Location timezone: {forecast.timezone}.",
        f"Average US AQI {window.us_aqi:.0f}; worst hourly AQI {window.max_aqi:.0f}; "
        f"PM2.5 {window.pm2_5:.1f} µg/m³.",
        f"Peak hourly rain chance {window.rain_probability:.0f}%; "
        f"temperature up to {window.temperature:.1f}°C.",
        f"Source: {source}. Forecast retrieved {fetched.isoformat()}.",
        "This event is a forecast snapshot and does not update. "
        "Re-check BLR Air before going outside; conditions can change.",
        "A best available window can still have unhealthy air and is not a guarantee of safety.",
        LIMITATION,
    ]
    if forecast.is_demo:
        description.insert(0, "OFFLINE DEMO: synthetic data; do not use for outdoor decisions.")
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//BLR Air//Outdoor Window//EN",
        "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        f"UID:{uuid5(NAMESPACE_URL, identity)}@blr-air",
        f"DTSTAMP:{fetched:%Y%m%dT%H%M%SZ}",
        f"DTSTART:{start:%Y%m%dT%H%M%SZ}",
        f"DTEND:{end:%Y%m%dT%H%M%SZ}",
        "SUMMARY:" + _text(f"{'DEMO — ' if forecast.is_demo else ''}BLR Air: {activity}"),
        "LOCATION:" + _text(location.name),
        "DESCRIPTION:" + _text("\n".join(description)),
    ]
    if reminder_minutes is not None:
        lines.extend(
            [
                "BEGIN:VALARM",
                f"TRIGGER:-PT{reminder_minutes}M",
                "ACTION:DISPLAY",
                "DESCRIPTION:Re-check BLR Air: forecast conditions may have changed.",
                "END:VALARM",
            ]
        )
    lines.extend(["END:VEVENT", "END:VCALENDAR"])
    payload = "\r\n".join(_fold(line) for line in lines) + "\r\n"
    try:
        # Exclusive creation rejects existing regular files and even dangling symlinks.
        with path.open("x", encoding="utf-8", newline="") as output:
            output.write(payload)
    except FileExistsError as exc:
        raise AirError(f"Calendar path already exists; refusing to overwrite: {path}") from exc
    except OSError as exc:
        raise AirError(f"Could not write calendar {path}: {exc.strerror or exc}") from exc
    return path
