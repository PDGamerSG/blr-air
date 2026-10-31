from dataclasses import replace
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from blr_air.domain import AirError, Forecast, Location, RequestSpec, Window
from blr_air.service import Recommendation


def recommendation(name="Central Park, New York"):
    zone = ZoneInfo("America/New_York")
    return Recommendation(
        RequestSpec(activity="walk"),
        Location(name, 40.7829, -73.9654, "America/New_York"),
        Forecast((), None, "America/New_York", datetime(2026, 10, 31, 12, tzinfo=UTC)),
        Window(
            datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0),
            datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1),
            110,
            35,
            20,
            25,
            120,
            150,
        ),
    )


def content(path):
    return path.read_bytes().decode("utf-8").replace("\r\n ", "")


def test_calendar_keeps_elapsed_hour_across_dst_and_includes_recheck_context(tmp_path):
    from blr_air.calendar_export import write_calendar

    path = tmp_path / "outdoor.ics"
    assert write_calendar(recommendation(), path) == path
    text = content(path)
    assert "DTSTART:20261101T053000Z\r\n" in text
    assert "DTEND:20261101T063000Z\r\n" in text
    assert "DTSTAMP:20261031T120000Z\r\n" in text
    assert "BEGIN:VTIMEZONE" not in text
    assert "America/New_York" in text
    assert "Open-Meteo" in text and "2026-10-31T12:00:00+00:00" in text
    assert "120" in text and "medical advice" in text
    assert "BEGIN:VALARM\r\nTRIGGER:-PT60M\r\n" in text
    assert "re-check" in text.lower()
    assert "does not update" in text.lower()


def test_calendar_escapes_text_instead_of_injecting_properties(tmp_path):
    from blr_air.calendar_export import write_calendar

    place = "Park\\Gate; North, Bengaluru\r\nEND:VEVENT\r\nBEGIN:VEVENT"
    path = write_calendar(recommendation(place), tmp_path / "escaped.ics")
    text = content(path)
    assert text.split("\r\n").count("BEGIN:VEVENT") == 1
    assert text.split("\r\n").count("END:VEVENT") == 1
    assert "LOCATION:Park\\\\Gate\\; North\\, Bengaluru\\nEND:VEVENT\\nBEGIN:VEVENT\r\n" in text


def test_calendar_folds_utf8_lines_at_75_octets_without_losing_text(tmp_path):
    from blr_air.calendar_export import write_calendar

    place = "ಬೆಂಗಳೂರು 🌳 " * 30
    path = write_calendar(recommendation(place), tmp_path / "unicode.ics")
    raw = path.read_bytes()
    lines = raw.split(b"\r\n")
    assert all(len(line) <= 75 for line in lines)
    assert any(line.startswith(b" ") for line in lines)
    assert all(line.decode("utf-8") is not None for line in lines)
    assert "LOCATION:" + place + "\r\n" in content(path)
    assert b"\n" not in raw.replace(b"\r\n", b"")


def test_uid_remains_stable_when_forecast_refreshes_but_changes_for_activity(tmp_path):
    from blr_air.calendar_export import write_calendar

    initial = recommendation()
    refreshed = replace(
        initial,
        forecast=replace(
            initial.forecast, fetched_at=initial.forecast.fetched_at + timedelta(hours=1)
        ),
    )
    changed = replace(initial, request=RequestSpec(activity="run"))
    uids = []
    for index, item in enumerate((initial, refreshed, changed)):
        text = content(write_calendar(item, tmp_path / f"event-{index}.ics"))
        uids.append(next(line for line in text.split("\r\n") if line.startswith("UID:")))
    assert uids[0] == uids[1]
    assert uids[0] != uids[2]


@pytest.mark.parametrize("existing", ["file", "symlink", "dangling-symlink"])
def test_calendar_never_overwrites_files_or_follows_symlinks(tmp_path, existing):
    from blr_air.calendar_export import write_calendar

    path = tmp_path / "event.ics"
    target = tmp_path / "target.ics"
    if existing == "file":
        path.write_text("keep me")
    else:
        if existing == "symlink":
            target.write_text("keep target")
        path.symlink_to(target)
    with pytest.raises(AirError, match="exist|overwrite|symlink"):
        write_calendar(recommendation(), path)
    if existing == "file":
        assert path.read_text() == "keep me"
    elif existing == "symlink":
        assert target.read_text() == "keep target"
    else:
        assert not target.exists()


def test_calendar_rejects_bad_suffix_and_reports_write_errors(tmp_path):
    from blr_air.calendar_export import write_calendar

    with pytest.raises(AirError, match=".ics"):
        write_calendar(recommendation(), tmp_path / "event.txt")
    with pytest.raises(AirError, match="write|directory|calendar"):
        write_calendar(recommendation(), tmp_path / "missing" / "event.ics")


def test_calendar_can_omit_alarm_and_labels_synthetic_forecast(tmp_path):
    from blr_air.calendar_export import write_calendar

    initial = recommendation()
    demo = replace(initial, forecast=replace(initial.forecast, is_demo=True))
    text = content(write_calendar(demo, tmp_path / "demo.ics", reminder_minutes=None))
    assert "VALARM" not in text
    assert "synthetic" in text.lower() and "do not use" in text.lower()


@pytest.mark.parametrize("minutes", [0, -1, True, 1.5])
def test_calendar_rejects_invalid_reminder_before_creating_file(tmp_path, minutes):
    from blr_air.calendar_export import write_calendar

    path = tmp_path / "event.ics"
    with pytest.raises(AirError, match="reminder|Reminder"):
        write_calendar(recommendation(), path, reminder_minutes=minutes)
    assert not path.exists()
