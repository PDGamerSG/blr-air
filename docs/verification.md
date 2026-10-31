# Verification record

Local checks performed on **31 October 2026**, using Python 3.12.14, uAgents 0.26.1 and uagents-core 0.4.12.

- **61 automated tests passed.** Ranking, contiguous windows, bounds, missing/invalid forecast values, provider retries, timezone/DST cases, parser and ASI failure behaviour, wire validation, chat acknowledgement/error/end-session semantics, private counters and CLI execution.
- **Ruff lint and format checks passed.**
- **Wheel and source distribution built successfully.** Discovery README is included in the installed package.
- **Live Koramangala CLI request passed.** A two-hour cycling recommendation returned current model AQI, PM2.5, future window, rain/temperature, timezone and attribution.
- **Live Melbourne CLI request passed.** Global geocoding resolved Melbourne, Victoria, Australia and returned a recommendation in Australia/Melbourne, including its +11:00 offset.
- **Real signed uAgents request/reply passed locally.** A separate caller identity sent `WindowRequest` to the running agent's `/submit` endpoint and received `WindowResponse` with status `ok` and a live two-hour forecast.
- **Local HTTP health check passed.** `/healthz` returned the expected address, mode and version.
- **Docker image built successfully**, using Python 3.12.16 on Linux; the installed CLI ran the complete offline demo as the non-root application user.

These tests establish local implementation and live-data functionality. They do not establish ASI:One routing, Agentverse account registration, ASI:One API balance, real-user tries, a feedback-driven change, contest submission or video evidence. ASI parser tests use controlled HTTP responses; no paid ASI call has been made without a configured key.

Developer test traffic is not evidence of outside adoption. Forecast values change, so this record records successful behaviour rather than a permanent recommended time.
