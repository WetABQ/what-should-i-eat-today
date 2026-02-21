#!/bin/bash

# Start the Telegram bot in background if token is set
if [ -n "$TELEGRAM_BOT_TOKEN" ]; then
    echo "Starting Telegram bot..."
    python bot.py &
fi

# Start the API server
echo "Starting API server on port ${PORT:-8000}..."
exec uvicorn src.api:app --host 0.0.0.0 --port ${PORT:-8000}
