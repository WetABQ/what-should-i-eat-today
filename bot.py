#!/usr/bin/env python3
"""Telegram Bot entry point for What Should I Eat Today."""

import logging
import os
import sys

from dotenv import load_dotenv

from src.telegram_bot import DiningBot

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main():
    """Main entry point for the Telegram bot."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        sys.exit(1)

    bot = DiningBot(token=token)
    bot.run(enable_daily_push=True)


if __name__ == "__main__":
    main()
