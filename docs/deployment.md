# Run continuously with a stable identity

The mailbox process must remain running. A laptop going to sleep makes the agent unavailable. Use a server you control or a container host with persistent storage. Only one process should use a given seed at a time.

## Local setup and registration

```sh
uv sync --frozen
uv run blr-air init
uv run blr-air doctor
uv run blr-air-agent
```

`init` creates `.env` with mode 0600. Back it up securely. Do not put it in Git or a container image. `AGENT_SEED_PHRASE` determines the agent address. `CALLER_SEED` identifies the separate demo planner. `ASI1_API_KEY` is optional and can be added without changing either identity.

Follow the startup Inspector link, then **Connect → Mailbox → Finish**. Verify the address matches `doctor` and the Agentverse dashboard says Active. Publish the supplied profile README and claim an available handle. Mailbox registration and ASI:One routing require your authenticated account; process logs alone do not establish either.

For the identity created in this workspace, the [Inspector connection link](https://agentverse.ai/inspect/?uri=http%3A//127.0.0.1%3A8001&address=agent1q2z89ttne7p57zq7r473lrc5jan899raacv6sjqj9eymk7kdqzkwkxhcwg3) points to the running Compose service. Open it on this machine while Docker is running. The current account-connection state is recorded in [verification.md](verification.md).

## Docker Compose on an always-on machine

Copy the project and the same private `.env` to the host. Stop the original process before starting the replacement.

```sh
docker compose up -d --build
docker compose logs --tail 100 agent
curl -fsS http://127.0.0.1:8001/healthz
docker compose exec agent blr-air stats
```

The service restarts automatically and stores usage plus uAgents state in `agent-data`. It runs as a non-root user. Port 8001 is exposed only on the host's loopback interface. Mailbox traffic is outbound, so no public endpoint or tunnel is required. When registering from a remote host, use SSH local forwarding for the Inspector:

```sh
ssh -L 8001:127.0.0.1:8001 your-server
```

Run only one copy of the identity. Check **Active** in Agentverse after migration. For a private local transport test that does not register publicly:

```sh
docker compose run --rm --service-ports agent --local
```

Stop the normal service first if it is using the same port or identity. `docker compose down` preserves the named volume; `down -v` destroys counters and state. The seed remains in `.env` outside the volume, so back up both separately.

## Health and recovery

- `/healthz` proves that the process is serving requests. It does not certify Open-Meteo, mailbox connectivity, discoverability or API balance.
- If ASI:One returns 402 or times out, documented English prompts still use local parsing. Fix billing/key configuration for freeform language support.
- If Open-Meteo fails, users receive an explicit retry message. There are bounded retries and a five-minute cache, without a fabricated or stale fallback.
- After a restart, requests work immediately; the cache is rebuilt and usage counters persist.
- The direct uAgents server binds all interfaces. Docker Compose limits exposure to loopback; for a non-container host, use its firewall to keep the Inspector and service port private.
- uAgents 0.26.1 mixes Pydantic v1 wire models with a v2 exception handler. `ResilientAgent` catches the missed v1 validation error, responds on the same session and leaves the queue running. The opt-in live checks send an invalid signed request to a disposable agent and then a valid one; an HTTP health response alone would not detect the original dead queue.
- Keep the process alive through judging. Use the host's own uptime monitoring and verify Active status in Agentverse regularly.

Changing an environment key requires `docker compose up -d --force-recreate`; merely restarting a container does not reload the env file. `SARVAM_API_KEY` is optional and used by the CLI and website voice paths. New clones can leave it empty. The existing agent address and `blr-air-window` wire schemas remain stable when enabling the separate `blr-air-plan` protocol.

## Updating

The optional website API is a separate `web` Compose service on `127.0.0.1:8082`; the signed agent keeps port 8001 and its identity. It supports forecast requests, venue lookup, calendar download and voice without routing through Agentverse. Use [agent-http-api.md](agent-http-api.md) when connecting a separately deployed static frontend. `SARVAM_API_KEY` is used by the CLI and this HTTP service, while the Agentverse chat channel remains text-only. `GOOGLE_PLACES_API_KEY` enables authentic venue data only when the provider accepts the key and project configuration.

```sh
git pull --ff-only
docker compose up -d --build
```

Preserve `.env` and the volume. To roll back, check out the previous code commit and rebuild. Do not regenerate the agent seed.
