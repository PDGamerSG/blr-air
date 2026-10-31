# BLR Air Window implementation

The accepted deliverable is a Python agent, tests, docs, and CLI. The user's instruction to build immediately supersedes additional design approval checkpoints.

The same service powers the CLI, Chat Protocol and typed agent requests. Open-Meteo provides current modelled AQI/PM2.5 and hourly AQI, PM2.5, rain probability and temperature. Built-in Bengaluru locality centroids precede global geocoding. HTTP calls are asynchronous and bounded; missing or invalid values are excluded, never converted to good conditions.

Select a contiguous one- or two-hour block entirely in the next 48 hours and between 05:00 and 21:00 in the location's timezone. Compare blocks by mean hourly heuristic cost: US AQI + 0.5 × PM2.5 + 1.5 × rain probability + 5 × degrees above 30°C. Break ties by earliest time. Report average AQI/PM2.5, peak rain/temperature, category, timezone, source and retrieval time. This is a transparent preference heuristic, not a health or exposure model. Current conditions must come from the provider's current section and have their own timestamp.

ASI:One is the only optional language model. Without a key, deterministic extraction supports the documented examples and free city names. No unrecognised city silently becomes Bengaluru. Today/tomorrow and morning/afternoon/evening constraints are honoured. Invalid duration, missing contiguous data and provider failures produce actionable responses.

The mailbox agent keeps its seed in a local ignored .env. The typed protocol returns a structured success or error response. Chat acknowledges messages, replies with text, closes the session, and never replies to acknowledgements. Usage stores counts and keyed sender hashes, never prompts or raw sender addresses.

Deployment includes a container, persistent data volume, health endpoint and restart instructions. No public registration, external feedback, demo video, contest submission or real-user evidence is claimed without being performed. The submission kit records these as pending external actions.
