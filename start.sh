#!/bin/bash

# Detect environment
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ -d "/app/src" ]; then
    # === Railway / Docker ===
    APP_DIR="/app"

    # Ensure data directories exist (important for mounted volumes)
    mkdir -p "$APP_DIR/data/cache" "$APP_DIR/data/presets"

    # Copy default preset if it doesn't exist (volume mount overrides /app/data)
    if [ ! -f "$APP_DIR/data/presets/default.json" ] && [ -f "$APP_DIR/default-preset.json" ]; then
        echo "Copying default preset to data directory..."
        cp "$APP_DIR/default-preset.json" "$APP_DIR/data/presets/default.json"
    fi

    echo "Data directory contents:"
    ls -la "$APP_DIR/data/"
    echo "Presets directory contents:"
    ls -la "$APP_DIR/data/presets/"
else
    # === Local ===
    APP_DIR="$SCRIPT_DIR"

    mkdir -p "$APP_DIR/data/cache" "$APP_DIR/data/presets"
fi

# Load .env if present
if [ -f "$APP_DIR/.env" ]; then
    echo "Loading .env..."
    set -a
    source "$APP_DIR/.env"
    set +a
fi

# Use uv locally, python in Docker
if command -v uv &> /dev/null && [ ! -d "/app/src" ]; then
    PY="uv run python"
else
    PY="python"
fi

# Start the Telegram bot in background if token is set
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    echo "Starting Telegram bot..."
    $PY "$APP_DIR/bot.py" &
fi

# Start the API server
PORT="${PORT:-8000}"
echo "Starting API server on port $PORT..."
exec $PY -m uvicorn src.api:app --host 0.0.0.0 --port "$PORT"
