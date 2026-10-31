FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 DATA_DIR=/data
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:0.9.7 /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock README.md LICENSE ./
COPY blr_air ./blr_air
RUN uv sync --frozen --no-dev --no-editable \
    && groupadd --gid 10001 air \
    && useradd --uid 10001 --gid air --create-home air \
    && mkdir -p /data \
    && chown air:air /data
ENV PATH="/app/.venv/bin:$PATH"
WORKDIR /data
USER air
EXPOSE 8001
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen('http://127.0.0.1:'+os.getenv('AGENT_PORT','8001')+'/healthz', timeout=4)"
ENTRYPOINT ["blr-air-agent"]
