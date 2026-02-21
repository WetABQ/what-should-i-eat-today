"""Telegram Bot for dining hall recommendations."""

import json
import logging
from datetime import date, time, timedelta
from pathlib import Path
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

# Subscribers storage
SUBSCRIBERS_FILE = Path(__file__).parent.parent / "data" / "subscribers.json"


def load_subscribers() -> set[int]:
    """Load subscriber chat IDs from file."""
    if not SUBSCRIBERS_FILE.exists():
        return set()
    try:
        with open(SUBSCRIBERS_FILE) as f:
            return set(json.load(f))
    except (json.JSONDecodeError, TypeError):
        return set()


def save_subscribers(subscribers: set[int]) -> None:
    """Save subscriber chat IDs to file."""
    SUBSCRIBERS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SUBSCRIBERS_FILE, "w") as f:
        json.dump(list(subscribers), f)


class DiningBot:
    """Telegram bot for dining hall recommendations."""

    def __init__(self, token: str):
        """Initialize the bot with token."""
        self.token = token
        self.config = Config()
        self.analyzer = get_analyzer()
        self.app: Application | None = None

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        chat_id = update.effective_chat.id
        is_subscribed = chat_id in load_subscribers()
        sub_status = "✅ Subscribed" if is_subscribed else "❌ Not subscribed"

        await update.message.reply_text(
            "🍽️ *What Should I Eat Today*\n\n"
            "I can help you find the best dining hall based on today's menu!\n\n"
            "*Commands:*\n"
            "/today - Get today's recommendations\n"
            "/tomorrow - Get tomorrow's recommendations\n"
            "/menu <hall> - View specific dining hall menu\n"
            "/halls - List available dining halls\n"
            "/subscribe - Subscribe to daily notifications\n"
            "/unsubscribe - Unsubscribe from daily notifications\n"
            "/config - View current configuration\n\n"
            f"*Daily Push:* {sub_status}\n\n"
            "Example: `/menu gordon-avenue-market`",
            parse_mode="Markdown",
        )

    async def subscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /subscribe command."""
        chat_id = update.effective_chat.id
        subscribers = load_subscribers()

        if chat_id in subscribers:
            await update.message.reply_text("✅ You're already subscribed to daily notifications!")
        else:
            subscribers.add(chat_id)
            save_subscribers(subscribers)
            await update.message.reply_text(
                "✅ Subscribed! You'll receive daily recommendations at 10:00 AM (Chicago time).\n\n"
                "Use /unsubscribe to stop notifications."
            )

    async def unsubscribe(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /unsubscribe command."""
        chat_id = update.effective_chat.id
        subscribers = load_subscribers()

        if chat_id in subscribers:
            subscribers.remove(chat_id)
            save_subscribers(subscribers)
            await update.message.reply_text("👋 Unsubscribed from daily notifications.")
        else:
            await update.message.reply_text("You're not subscribed to daily notifications.")

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
        """Send daily recommendation push to all subscribers."""
        subscribers = load_subscribers()
        if not subscribers:
            logger.info("No subscribers for daily push")
            return

        try:
            # Build messages for all meal types
            messages = []
            for meal_type in self.config.meal_types:
                menu_day = await fetch_all_menus(date.today(), [meal_type])
                recommendation = self.analyzer.analyze_day(menu_day, meal_type)
                message = self.analyzer.format_recommendation(recommendation, verbose=True)
                messages.append(message)

            # Send to all subscribers
            for chat_id in subscribers:
                try:
                    for message in messages:
                        await context.bot.send_message(chat_id=chat_id, text=message)
                except Exception as e:
                    logger.warning(f"Failed to send to {chat_id}: {e}")
                    # Remove invalid chat IDs
                    if "chat not found" in str(e).lower() or "blocked" in str(e).lower():
                        subscribers.discard(chat_id)
                        save_subscribers(subscribers)

            logger.info(f"Daily push sent to {len(subscribers)} subscribers")
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
        self.app.add_handler(CommandHandler("subscribe", self.subscribe))
        self.app.add_handler(CommandHandler("unsubscribe", self.unsubscribe))
        self.app.add_handler(CommandHandler("config", self.show_config))
        self.app.add_handler(CommandHandler("refresh", self.refresh))

        # Schedule daily push
        if enable_daily_push:
            self._schedule_daily_push(self.app)

        # Run the bot
        logger.info("Starting bot...")
        self.app.run_polling()
