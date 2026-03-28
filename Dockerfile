FROM python:3.13-slim

# Install supercronic for cron jobs
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://github.com/aptible/supercronic/releases/download/v0.2.33/supercronic-linux-amd64 \
       -o /usr/local/bin/supercronic \
    && chmod +x /usr/local/bin/supercronic

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

# Install dependencies only (cached layer — no project source needed)
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# Copy application code then install the project itself
COPY src/ src/
COPY deploy/ deploy/
RUN uv sync --frozen --no-dev

# Make entrypoint executable
RUN chmod +x deploy/entrypoint.sh

EXPOSE 8080

CMD ["deploy/entrypoint.sh"]
