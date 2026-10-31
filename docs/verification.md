# Verification record

Local checks performed on **31 October 2026**, using Python 3.12.14, uAgents 0.26.1 and uagents-core 0.4.12.

- **74 automated tests passed.** Ranking, contiguous windows, bounds, missing/invalid forecast values, provider retries, timezone/DST cases, parser and ASI failure behaviour, wire validation, chat acknowledgement/error/end-session semantics, private counters and CLI execution.
- **Independent code review completed.** Fixed and regression-tested local period end boundaries, alternate city phrasing, unsupported time constraints and incomplete ASI extractions that could otherwise default to Bengaluru.
- **Ruff lint and format checks passed.**
- **Wheel and source distribution built successfully.** Discovery README is included in the installed package.
- **Live Koramangala CLI request passed.** A two-hour cycling recommendation returned current model AQI, PM2.5, future window, rain/temperature, timezone and attribution.
- **Live Melbourne CLI request passed.** Global geocoding resolved Melbourne, Victoria, Australia and returned a recommendation in Australia/Melbourne, including its +11:00 offset.
- **Real signed uAgents request/reply passed locally.** A separate caller identity sent `WindowRequest` to the running agent's `/submit` endpoint and received `WindowResponse` with status `ok` and a live two-hour forecast.
- **Local HTTP health check passed.** `/healthz` returned the expected address, mode and version.
- **Docker image built successfully**, using Python 3.12.16 on Linux; the installed CLI ran the complete offline demo as the non-root application user.
- **Container health and signed live request passed.** The Docker healthcheck reported `healthy`; the caller received a live successful typed response through the container's loopback-published port.
- **Public repository created and pushed:** https://github.com/PDGamerSG/blr-air. Private `.env`, generated state, virtualenv and the pre-existing research notes are excluded from Git.
- **GitHub CI passed on Python 3.12 and 3.13:** [initial CI run](https://github.com/PDGamerSG/blr-air/actions/runs/41183700358).
- **Mailbox deployment started in Docker Compose.** Health responds in mailbox mode; both protocol manifests were published and Almanac API registration succeeded. The provider logs report `Agent mailbox not found: create one using the agent inspector`. Account connection remains pending.
- **Real ASI:One integration verified.** `asi1-mini` returned HTTP 200 and correctly extracted a two-hour run in HSR tomorrow morning from a Hindi/English request. The complete CLI path then returned a live forecast for HSR Layout with those constraints. The private key is stored only in the ignored, mode-0600 `.env`; the running container was recreated with the configured parser and its original agent identity.

These tests establish local implementation, live-data functionality and authenticated ASI:One API parsing. They do not establish routing through the ASI:One chat product, Agentverse account registration, real-user tries, a feedback-driven change, contest submission or video evidence. Automated ASI parser tests use controlled HTTP responses; the authenticated integration was also tested separately with the configured key.

Developer test traffic is not evidence of outside adoption. Forecast values change, so this record records successful behaviour rather than a permanent recommended time.
