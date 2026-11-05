# Implementation plan

1. Test and implement validated requests, timezone-aware contiguous-window ranking, categories and forecast merging.
2. Test and implement localities, global geocoding, bounded HTTP retries, deterministic and ASI:One parsing, and shared response formatting.
3. Test and implement CLI text/JSON/offline demo, typed uAgents models, chat acknowledgement/reply/error paths and private usage counters.
4. Add mailbox launch, typed caller, stable identity setup, health checks, Docker/CI, discovery README and honest submission/evidence templates.
5. Run deterministic tests, lint, packaging checks, a real local two-agent exchange, and live CLI requests for Bengaluru and another timezone.

Acceptance: documented commands work on Python 3.12; no key needed for the CLI; the same forecast logic powers chat and typed messages; failures remain explicit; no past/gapped/null-filled window is recommended; secrets are ignored; external steps remain clearly distinguished from local verification.
