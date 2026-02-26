"""Telegram Bot for dining hall recommendations."""

import logging
import os
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

# Always use Chicago timezone
CHICAGO_TZ = ZoneInfo("America/Chicago")


def today_cst() -> datetime:
    """Get today's date in Chicago timezone."""
    return datetime.now(CHICAGO_TZ).date()


def tomorrow_cst() -> datetime:
    """Get tomorrow's date in Chicago timezone."""
    return today_cst() + timedelta(days=1)

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

# Bot commands for menu
BOT_COMMANDS = [
    BotCommand("today", "Get today's dining recommendations"),
    BotCommand("tomorrow", "Get tomorrow's recommendations"),
    BotCommand("menu", "View specific dining hall menu"),
    BotCommand("halls", "List available dining halls"),
    BotCommand("push", "Push today's menu to channel (test)"),
    BotCommand("config", "View current configuration"),
    BotCommand("help", "Show help message"),
]

from .analyzer import Config, get_analyzer
from .scraper import (
    fetch_all_menus,
    fetch_daily_menu,
    get_active_dining_halls,
    get_dining_hall_by_slug,
)

logger = logging.getLogger(__name__)


class DiningBot:
    """Telegram bot for dining hall recommendations."""

    def __init__(self, token: str, channel_id: str | None = None):
        """Initialize the bot with token.

        Args:
            token: Telegram bot token
            channel_id: Channel ID or username (e.g., @my_channel) for daily push
        """
        self.token = token
        self.channel_id = channel_id or os.getenv("TELEGRAM_CHANNEL_ID")
        self.config = Config()
        self.analyzer = get_analyzer()
        self.app: Application | None = None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        await self.help(update, context)

    async def help(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        channel_info = f"Channel: {self.channel_id}" if self.channel_id else "No channel configured"

        await update.message.reply_text(
            "🍽️ *What Should I Eat Today*\n\n"
            "I help you find the best dining hall based on today's menu!\n\n"
            "*Commands:*\n"
            "/today - Get today's recommendations\n"
            "/tomorrow - Get tomorrow's recommendations\n"
            "/menu <hall> - View specific dining hall menu\n"
            "/halls - List available dining halls\n"
            "/config - View current configuration\n"
            "/help - Show this help message\n\n"
            f"*Daily Push:* {channel_info}\n\n"
            "Example: `/menu gordon-avenue-market`",
            parse_mode="Markdown",
        )

    async def today(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /today command - returns both lunch and dinner."""
        target_date = today_cst()
        await update.message.reply_text(f"🔄 Fetching menus for {target_date} (CST)...")

        try:
            # Fetch and send both lunch and dinner
            for meal_type in ["lunch", "dinner"]:
                menu_day = await fetch_all_menus(target_date, [meal_type])
                recommendation = self.analyzer.analyze_day(menu_day, meal_type)
                response = self.analyzer.format_recommendation(recommendation)
                await update.message.reply_text(response, parse_mode="Markdown")
        except Exception as e:
            logger.exception("Error fetching menus")
            await update.message.reply_text(f"❌ Error fetching menus: {e}")

    async def tomorrow(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tomorrow command - returns both lunch and dinner."""
        target_date = tomorrow_cst()
        await update.message.reply_text(f"🔄 Fetching menus for {target_date} (CST)...")

        try:
            # Fetch and send both lunch and dinner
            for meal_type in ["lunch", "dinner"]:
                menu_day = await fetch_all_menus(target_date, [meal_type])
                recommendation = self.analyzer.analyze_day(menu_day, meal_type)
                response = self.analyzer.format_recommendation(recommendation)
                await update.message.reply_text(response, parse_mode="Markdown")
        except Exception as e:
            logger.exception("Error fetching menus")
            await update.message.reply_text(f"❌ Error fetching menus: {e}")

    async def menu(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /menu command."""
        if not context.args:
            halls = get_active_dining_halls()
            hall_list = "\n".join([f"• `{h.slug}`" for h in halls])
            await update.message.reply_text(
                f"Please specify a dining hall:\n\n{hall_list}\n\n"
                "Example: `/menu gordon-avenue-market`",
                parse_mode="Markdown",
            )
            return

        hall_slug = context.args[0]
        meal_type = context.args[1] if len(context.args) > 1 else "lunch"

        hall = get_dining_hall_by_slug(hall_slug)
        if not hall:
            await update.message.reply_text(f"❌ Unknown dining hall: {hall_slug}")
            return

        await update.message.reply_text(f"🔄 Fetching menu for {hall.name}...")

        try:
            daily_menu = await fetch_daily_menu(hall, date.today(), [meal_type])
            response = self.analyzer.format_menu(daily_menu, meal_type)
            await update.message.reply_text(response)
        except Exception as e:
            logger.exception("Error fetching menu")
            await update.message.reply_text(f"❌ Error fetching menu: {e}")

    async def halls(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /halls command."""
        halls = get_active_dining_halls()
        lines = ["🏫 *Available Dining Halls:*\n"]
        for hall in halls:
            status = "✅" if hall.active else "❌"
            lines.append(f"{status} {hall.name}")
            lines.append(f"   `{hall.slug}`")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def show_config(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /config command."""
        config = self.config
        from .storage import get_storage

        storage = get_storage()
        ratings_count = len(storage.get_ratings_dict())

        response = (
            "⚙️ *Current Configuration*\n\n"
            f"*Rated items:* {ratings_count}\n"
            f"*Meal types:* {', '.join(config.meal_types)}\n"
            f"*Push time:* {config.telegram.get('daily_push_time', 'Not set')}\n"
            f"*Channel:* {self.channel_id or '(none)'}"
        )
        await update.message.reply_text(response, parse_mode="Markdown")

    async def refresh(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /refresh command."""
        self.config.reload()
        await update.message.reply_text("✅ Configuration reloaded!")

    async def push(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /push command - manually push to channel for testing."""
        if not self.channel_id:
            await update.message.reply_text("❌ No channel configured. Set TELEGRAM_CHANNEL_ID.")
            return

        target_date = today_cst()
        await update.message.reply_text(f"🔄 Pushing {target_date} (CST) to channel {self.channel_id}...")

        try:
            for meal_type in ["lunch", "dinner"]:
                menu_day = await fetch_all_menus(target_date, [meal_type])
                recommendation = self.analyzer.analyze_day(menu_day, meal_type)
                message = self.analyzer.format_recommendation(recommendation)

                await context.bot.send_message(
                    chat_id=self.channel_id,
                    text=message,
                    parse_mode="Markdown",
                )

            await update.message.reply_text(f"✅ Pushed to {self.channel_id}")
        except Exception as e:
            logger.exception("Error pushing to channel")
            await update.message.reply_text(f"❌ Error: {e}")

    async def send_daily_push(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send daily recommendation push to channel."""
        if not self.channel_id:
            logger.info("No channel configured for daily push")
            return

        target_date = today_cst()
        try:
            # Send both lunch and dinner
            for meal_type in ["lunch", "dinner"]:
                menu_day = await fetch_all_menus(target_date, [meal_type])
                recommendation = self.analyzer.analyze_day(menu_day, meal_type)
                message = self.analyzer.format_recommendation(recommendation)

                await context.bot.send_message(
                    chat_id=self.channel_id,
                    text=message,
                    parse_mode="Markdown",
                )

            logger.info(f"Daily push sent to channel {self.channel_id} for {target_date}")
        except Exception as e:
            logger.exception(f"Error sending daily push to channel: {e}")

    def _schedule_daily_push(self, app: Application) -> None:
        """Schedule daily push job."""
        telegram_config = self.config.telegram
        push_time_str = telegram_config.get("daily_push_time", "10:00")
        timezone_str = telegram_config.get("timezone", "America/Chicago")

        try:
            hour, minute = map(int, push_time_str.split(":"))
            tz = ZoneInfo(timezone_str)
            push_time = time(hour=hour, minute=minute, tzinfo=tz)

            app.job_queue.run_daily(
                self.send_daily_push,
                time=push_time,
                name="daily_recommendation",
            )
            logger.info(f"Scheduled daily push at {push_time_str} {timezone_str}")
        except Exception as e:
            logger.exception("Failed to schedule daily push")

    async def post_init(self, app: Application) -> None:
        """Set up bot commands after initialization."""
        await app.bot.set_my_commands(BOT_COMMANDS)
        logger.info("Bot commands registered")

    def run(self, enable_daily_push: bool = True) -> None:
        """Run the bot."""
        self.app = Application.builder().token(self.token).post_init(self.post_init).build()

        # Add command handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("help", self.help))
        self.app.add_handler(CommandHandler("today", self.today))
        self.app.add_handler(CommandHandler("tomorrow", self.tomorrow))
        self.app.add_handler(CommandHandler("menu", self.menu))
        self.app.add_handler(CommandHandler("halls", self.halls))
        self.app.add_handler(CommandHandler("push", self.push))
        self.app.add_handler(CommandHandler("config", self.show_config))
        self.app.add_handler(CommandHandler("refresh", self.refresh))

        # Schedule daily push
        if enable_daily_push:
            self._schedule_daily_push(self.app)

        # Run the bot
        logger.info("Starting bot...")
        self.app.run_polling()
