# BLR Air Window

**AQI, PM2.5, rain and heat → a better time to go outside.** Finds the best available 1–2 hour window in the next 48 hours to run, cycle, walk, commute or take children outside in Bengaluru or another city.

![tag:innovationlab](https://img.shields.io/badge/innovationlab-3D8BD3)
![tag:hackathon](https://img.shields.io/badge/hackathon-5F43F1)
![tag:domain/utility](https://img.shields.io/badge/utility-4CAF50)

Uses live, keyless Open-Meteo forecasts. All replies identify the location, timezone, data retrieval time and source. This is **modelled air quality, not CPCB station readings**. A best available window can still have unhealthy air; the agent says so. It does not provide medical advice.

Public repository: [PDGamerSG/blr-air](https://github.com/PDGamerSG/blr-air). See the [verification record](docs/verification.md) for completed checks and external steps still to verify.

## Run it now

Python **3.12 or 3.13** is required. With [uv](https://docs.astral.sh/uv/):

```sh
uv sync --extra dev
uv run blr-air 'best 1-hour window to run in HSR Layout'
uv run blr-air 'best 2-hour cycling window in Koramangala tomorrow morning'
uv run blr-air --place 'Melbourne, Australia' --activity walk --json
```

Or use pip:

```sh
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
python -m blr_air 'best window in Whitefield'
```

No keys are needed for these commands. `--demo` exercises the same recommendation service with **clearly labelled synthetic Bengaluru data**, without making network calls:

```sh
python -m blr_air --demo --hours 2 --json
python -m blr_air --latitude 12.9116 --longitude 77.6389 --hours 2
python -m blr_air --place 'New York, US' --day tomorrow --period morning
```

Inputs support `run`, `cycle`, `walk`, `commute`, `kids`; duration `1` or `2`; day `next48`, `today`, `tomorrow`; period `any`, `morning`, `afternoon`, `evening`. Exact clock-time requests are rejected with guidance. CLI errors return nonzero exit codes. Use `--json` for structured results.

## Run the Agentverse mailbox agent

```sh
python -m blr_air init
python -m blr_air doctor
python agent.py
```

`init` creates a private, ignored `.env` with unique agent and caller seeds. It never overwrites an existing file. **Back up the seed; it determines your address.** Keep it unchanged when moving to an always-on host. `doctor` prints the public address without printing secrets.

1. Optionally set `ASI1_API_KEY` in `.env` for freeform/multilingual parsing using **asi1-mini**. ASI:One is the only model integration. No key, invalid output, unavailable API or HTTP 402 uses the deterministic English parser.
2. Open the Inspector URL printed by `python agent.py`. Choose **Connect → Mailbox → Finish**. Allow local-network access if your browser asks. Confirm registration and **Active** status on Agentverse; local process health alone does not prove this.
3. Set profile name **BLR Air Window**, claim `@blr-air` if available, upload an avatar, and publish [AGENT_README.md](AGENT_README.md). The handle is a profile setting; running the code does not claim it.
4. In ASI:One, enable **Agents** and use the profile's **Chat with Agent** link. Paste one of the prompts below. Save the actual share link from your account.

```text
@blr-air best 1-hour window to run in HSR Layout
@blr-air best 2-hour cycling window in Koramangala
@blr-air when is the air cleanest in Whitefield
@blr-air can I take children outside in Melbourne tomorrow morning
```

The profile link, ASI:One share link and Active status must be verified after registration. They are not inferred from a local run.

## Agents and typed API

| Agent | Purpose | Address |
| --- | --- | --- |
| `blr-air` | Chat Protocol and typed forecast requests | `agent1q2z89ttne7p57zq7r473lrc5jan899raacv6sjqj9eymk7kdqzkwkxhcwg3` |
| `day-planner-demo` | Hires BLR Air using the shared wire models | `agent1qtehmnqextcf6czcujeq3yfh5umr2qtz4cxyxknve5tlcxgdkmpdgp4x53p` |

These are the identities generated for this build; Agentverse account connection and ASI:One routing still need verification. A fresh clone's `init` creates its own identities. The original seeds stay private. A ready-to-upload avatar is in [assets/avatar.png](assets/avatar.png).

Protocol: **`blr-air-window` v0.1.0**. Import `WindowRequest` and `WindowResponse` from `blr_air.models` (or the root `models.py` compatibility module).

```python
request = WindowRequest(latitude=12.9116, longitude=77.6389, hours=2,
                        activity="run", day="tomorrow", period="morning")
await ctx.send(BLR_AIR_ADDRESS, request)
```

Success returns `status="ok"`, offset-aware `start`/`end`, `timezone`, mean `us_aqi`/`pm2_5`, peak `rain_probability`/`temperature`, `max_aqi`, `fetched_at`, `source`, and a readable `summary`. Always check status first. A valid request that cannot be fulfilled returns `status="error"`, `error_code`, and `summary`; measurements remain null. Invalid coordinates or durations are rejected by the wire schema.

Set `BLR_AIR_ADDRESS` in `.env`, then `python caller.py`. Connect its own Inspector/mailbox too. The caller sends once after 30 seconds; after first-time registration restart it if needed to demonstrate the response.

For a fully local signed agent-message exchange, start `python agent.py --local`, copy the address from `doctor`, and run:

```sh
python caller.py --address YOUR_AGENT_ADDRESS --endpoint http://127.0.0.1:8001/submit
curl -fsS http://127.0.0.1:8001/healthz
```

Local mode does not publish or register the agent. The caller uses its own cryptographic identity. This exercises real uAgents message envelopes, schema validation and the same live forecast service used by the mailbox.

## How the recommendation is chosen

Fetch four calendar days to cover the next **48 elapsed hours**, even late in the day. Join hourly air and weather data by UTC timestamp, then select complete consecutive blocks. Missing rain, temperature, AQI or PM2.5 excludes that hour; it is never assumed to be zero. Past hours and windows ending outside the horizon are excluded.

Only **05:00–21:00 local** windows are eligible. This is an activity-hours preference, **not a sunrise/sunset calculation**. Morning is 05:00–12:00, afternoon 12:00–17:00, evening 17:00–21:00. A request with no eligible window returns an explanation, never a nighttime fallback. Dates and DST use the provider's IANA timezone.

Lower mean hourly score wins, then earlier time breaks ties:

```text
US AQI + 0.5 × PM2.5 + 1.5 × rain probability + 5 × max(0, temperature °C − 30)
```

This is a documented **preference heuristic**, not a validated medical/exposure formula. AQI already includes particulate pollution; the PM2.5 term deliberately adds weight to particulates. Activity changes the wording, not an invented medical risk score. The reported rain chance is the **maximum hourly chance**, not the probability of rain over the entire block. Risk language uses the worst hourly AQI rather than averaging away a bad hour.

Twenty Bengaluru locality centroids are built in, including HSR Layout, Koramangala, Whitefield, Indiranagar, Electronic City, Jayanagar, Bellandur, Hebbal and Cubbon Park. Other names use Open-Meteo geocoding. Use `city, country` or coordinates to disambiguate; the resolved administrative area and country are shown. Model grid resolution does not provide street-level precision.

## Reliability, privacy and deployment

HTTP requests have six-second timeouts, at most three attempts for transient failures, a 23-second forecast budget, and a five-minute bounded forecast cache. There is no stale-data fallback. The timestamp on current model values is distinct from forecast retrieval time. Chat sends an acknowledgement, a text answer and `EndSessionContent`; acknowledgements are never answered.

Usage counters persist in `data/usage.sqlite`. Sender identifiers are keyed SHA-256 hashes; prompts and raw addresses are not saved by application telemetry. Unique senders are **not verified unique people**. The Inspector keeps recent envelopes in process memory for debugging; application message history is not persisted. Agentverse and ASI:One have their own data policies. `python -m blr_air stats` reports aggregate queries and outcomes.

See [deployment instructions](docs/deployment.md) for Docker, persistent identity and an always-on service. `/healthz` reports process liveness, not external service availability or Agentverse registration. The initial mailbox agent runs from this directory; production keeps all state in a dedicated volume.

## Verify

```sh
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run blr-air --demo --json
```

Tests cover window boundaries, missing values, retries, timezone/DST behaviour, parsing, schema validation, chat/error semantics, telemetry persistence and CLI execution. See [verification record](docs/verification.md) for the checks actually performed on this build.

## Hackathon evidence

The [submission kit](docs/submission.md) includes ten evaluation prompts, a routing experiment, outside-test notes, deployment checks and demo scripts. [Feedback log](docs/feedback.md) starts empty: there are no invented tester notes, users, videos, endorsements or challenge-completion claims. Record actual usage counts after deployment; local development messages are not outside-user tries.

## Credits and licence

Code: MIT; see [LICENSE](LICENSE). Weather/geocoding: [Open-Meteo](https://open-meteo.com/). Air-quality forecasts: [Open-Meteo Air Quality API](https://open-meteo.com/en/docs/air-quality-api), based on [CAMS](https://atmosphere.copernicus.eu/). Follow the [Open-Meteo attribution and API terms](https://open-meteo.com/en/terms); the free endpoint is intended for noncommercial use. Language parsing: [ASI:One](https://asi1.ai/), optional. Agent transport: [Fetch.ai uAgents](https://github.com/fetchai/uAgents).
