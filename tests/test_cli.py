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
