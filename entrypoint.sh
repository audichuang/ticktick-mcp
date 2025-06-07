#!/bin/bash
set -e

# Setup credentials from environment if not already present
if [ ! -f /app/.env ]; then
    echo "No .env file found, attempting to create from environment variables..."
    python -m ticktick_mcp.src.non_interactive_auth
fi

# Source the .env file if it exists
if [ -f /app/.env ]; then
    set -a
    source /app/.env
    set +a
fi

# Start the remote server
exec python -m ticktick_mcp.src.remote_server