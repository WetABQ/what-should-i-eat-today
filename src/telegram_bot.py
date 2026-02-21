"""Telegram Bot for dining hall recommendations."""

import asyncio
import logging
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
)

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

    def __init__(self, token: str, chat_id: str | None = None):
        """Initialize the bot with token and optional chat ID."""
        self.token = token
        self.chat_id = chat_id
        self.config = Config()
        self.analyzer = get_analyzer()
        self.app: Application | None = None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        await update.message.reply_text(
            "🍽️ *What Should I Eat Today*\n\n"
            "I can help you find the best dining hall based on today's menu!\n\n"
            "*Commands:*\n"
            "/today - Get today's recommendations\n"
            "/tomorrow - Get tomorrow's recommendations\n"
            "/menu <hall> - View specific dining hall menu\n"
            "/halls - List available dining halls\n"
            "/config - View current configuration\n"
            "/refresh - Refresh menu data\n\n"
            "Example: `/menu gordon-avenue-market`",
            parse_mode="Markdown",
        )

    async def today(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /today command."""
        meal_type = "lunch"
        if context.args:
            meal_type = context.args[0].lower()
            if meal_type not in ["breakfast", "lunch", "dinner"]:
                meal_type = "lunch"

        await update.message.reply_text("🔄 Fetching today's menus...")

        try:
            menu_day = await fetch_all_menus(date.today(), [meal_type])
            recommendation = self.analyzer.analyze_day(menu_day, meal_type)
            response = self.analyzer.format_recommendation(recommendation, verbose=True)
            await update.message.reply_text(response)
        except Exception as e:
            logger.exception("Error fetching menus")
            await update.message.reply_text(f"❌ Error fetching menus: {e}")

    async def tomorrow(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /tomorrow command."""
        meal_type = "lunch"
        if context.args:
            meal_type = context.args[0].lower()
            if meal_type not in ["breakfast", "lunch", "dinner"]:
                meal_type = "lunch"

        await update.message.reply_text("🔄 Fetching tomorrow's menus...")

        try:
            tomorrow_date = date.today() + timedelta(days=1)
            menu_day = await fetch_all_menus(tomorrow_date, [meal_type])
            recommendation = self.analyzer.analyze_day(menu_day, meal_type)
            response = self.analyzer.format_recommendation(recommendation, verbose=True)
            await update.message.reply_text(response)
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
        active_preset = storage.get_active_preset()

        response = (
            "⚙️ *Current Configuration*\n\n"
            f"*Active preset:* {active_preset or '(none)'}\n"
            f"*Rated items:* {ratings_count}\n"
            f"*Meal types:* {', '.join(config.meal_types)}\n"
            f"*Push time:* {config.telegram.get('daily_push_time', 'Not set')}"
        )
        await update.message.reply_text(response, parse_mode="Markdown")

    async def refresh(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /refresh command."""
        self.config.reload()
        await update.message.reply_text("✅ Configuration reloaded!")

    async def send_daily_push(self, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Send daily recommendation push with full ranking details."""
        if not self.chat_id:
            logger.warning("No chat ID configured for daily push")
            return

        try:
            for meal_type in self.config.meal_types:
                menu_day = await fetch_all_menus(date.today(), [meal_type])
                recommendation = self.analyzer.analyze_day(menu_day, meal_type)
                message = self.analyzer.format_recommendation(recommendation, verbose=True)
                await context.bot.send_message(chat_id=self.chat_id, text=message)
        except Exception as e:
            logger.exception("Error sending daily push")

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

    def run(self, enable_daily_push: bool = True) -> None:
        """Run the bot."""
        self.app = Application.builder().token(self.token).build()

        # Add command handlers
        self.app.add_handler(CommandHandler("start", self.start))
        self.app.add_handler(CommandHandler("today", self.today))
        self.app.add_handler(CommandHandler("tomorrow", self.tomorrow))
        self.app.add_handler(CommandHandler("menu", self.menu))
        self.app.add_handler(CommandHandler("halls", self.halls))
        self.app.add_handler(CommandHandler("config", self.show_config))
        self.app.add_handler(CommandHandler("refresh", self.refresh))

        # Schedule daily push
        if enable_daily_push and self.chat_id:
            self._schedule_daily_push(self.app)

        # Run the bot
        logger.info("Starting bot...")
        self.app.run_polling()
