import json
import os
import subprocess
import sys
from pathlib import Path

from blr_air.cli import initialize

ROOT = Path(__file__).resolve().parents[1]


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-m", "blr_air", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=20,
        env={**os.environ, "ASI1_API_KEY": ""},
    )


def test_demo_json_runs_the_full_service_and_labels_synthetic_data():
    result = run_cli("--demo", "--json", "--hours", "2")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["status"] == "ok"
    assert data["request"]["hours"] == 2
    assert data["mode"] == "synthetic-demo"
    assert "synthetic" in data["source"].lower()


def test_demo_comparison_json_ranks_places_and_returns_backups():
    result = run_cli("compare HSR Layout and Whitefield for a run", "--demo", "--json")
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["status"] == "ok"
    assert len(data["places"]) == 2
    assert data["places"][0]["rank"] == 1
    assert len(data["places"][0]["backups"]) >= 1


def test_cli_rejects_unpaired_coordinates_with_nonzero_exit():
    result = run_cli("--latitude", "12.91", "--json")
    assert result.returncode != 0
    assert "longitude" in result.stderr.lower()


def test_setup_creates_private_seeds_and_never_overwrites_existing_identity(tmp_path):
    path = tmp_path / ".env"
    initialize(path)
    first = path.read_bytes()
    assert b"AGENT_SEED_PHRASE=" in first
    assert path.stat().st_mode & 0o777 == 0o600
    initialize(path)
    assert path.read_bytes() == first


def test_cli_explicit_comparison_flags_and_limits():
    result = run_cli(
        "--compare",
        "HSR Layout",
        "--compare",
        "Whitefield",
        "--demo",
        "--max-aqi",
        "100",
        "--max-rain",
        "30",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert len(data["places"]) == 2
    for place in data["places"]:
        assert place["window"]["max_aqi"] <= 100
        assert place["window"]["rain_probability"] <= 30


def test_cli_impossible_threshold_returns_error_not_a_relaxed_window():
    result = run_cli("--demo", "--max-aqi", "1", "--json")
    assert result.returncode == 1
    assert json.loads(result.stdout)["status"] == "error"


def test_cli_coordinate_request_cannot_silently_discard_comparison():
    result = run_cli(
        "compare HSR Layout and Whitefield", "--latitude", "12.9", "--longitude", "77.6"
    )
    assert result.returncode != 0


def test_cli_writes_single_event_calendar_for_selected_window(tmp_path):
    path = tmp_path / "run.ics"
    result = run_cli("--demo", "--calendar", str(path), "--json")
    assert result.returncode == 0, result.stderr
    assert "BEGIN:VEVENT" in path.read_text()
    assert json.loads(result.stdout)["calendar_file"] == str(path)


def test_offline_demo_can_exercise_daylight_and_weather_limits():
    result = run_cli(
        "--demo",
        "--daylight-only",
        "--max-uv",
        "5",
        "--max-wind",
        "20",
        "--max-temperature",
        "30",
        "--json",
    )
    assert result.returncode == 0, result.stderr
    window = json.loads(result.stdout)["window"]
    assert window["daylight"] is True
    assert window["uv_index"] <= 5 and window["apparent_temperature"] <= 30
