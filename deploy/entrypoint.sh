#!/bin/sh
set -e

# Run initial sync if cache is empty
if [ ! -f /data/_index.json ]; then
    echo "First run: syncing articles..."
    uv run antientropy-sync --cache-dir /data 2>&1
fi

# Start supercronic in background for daily sync
supercronic /app/deploy/crontab &

# Start MCP server
exec uv run python -m antientropy_mcp
