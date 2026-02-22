#!/bin/bash

# Ensure data directories exist (important for mounted volumes)
mkdir -p /app/data/cache /app/data/presets

# Copy default preset if it doesn't exist (volume mount overrides /app/data)
if [ ! -f /app/data/presets/default.json ] && [ -f /app/default-preset.json ]; then
    echo "Copying default preset to data directory..."
    cp /app/default-preset.json /app/data/presets/default.json
fi

echo "Data directory contents:"
ls -la /app/data/
echo "Presets directory contents:"
ls -la /app/data/presets/

# Start the Telegram bot in background if token is set
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    echo "Starting Telegram bot..."
    python bot.py &
fi

# Start the API server
echo "Starting API server on port ${PORT:-8000}..."
exec uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000}
