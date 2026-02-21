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
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set")
        sys.exit(1)

    if not chat_id:
        logger.warning("TELEGRAM_CHAT_ID not set, daily push will be disabled")

    bot = DiningBot(token=token, chat_id=chat_id)
    bot.run(enable_daily_push=bool(chat_id))


if __name__ == "__main__":
    main()
