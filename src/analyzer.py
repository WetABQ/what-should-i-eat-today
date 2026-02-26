"""Menu analysis and recommendation logic."""

import re
from pathlib import Path

import yaml

from .models import (
    DailyMenu,
    DailyRecommendation,
    DiningHallScore,
    MenuItem,
    MenuDay,
)
from .storage import get_storage

CONFIG_PATH = Path(__file__).parent.parent / "config.yaml"


class Config:
    """Configuration loaded from config.yaml."""

    def __init__(self, config_path: Path | None = None):
        """Load configuration from YAML file."""
        self.config_path = config_path or CONFIG_PATH
        self._config: dict = {}
        self.reload()

    def reload(self) -> None:
        """Reload configuration from file."""
        if self.config_path.exists():
            with open(self.config_path) as f:
                self._config = yaml.safe_load(f) or {}
        else:
            self._config = {}

    @property
    def always_available(self) -> list[str]:
        """Get list of always available items to filter out."""
        return self._config.get("always_available", [])

    @property
    def dining_halls(self) -> list[str]:
        """Get list of dining hall slugs to analyze."""
        return self._config.get("dining_halls", [])

    @property
    def meal_types(self) -> list[str]:
        """Get list of meal types to analyze."""
        return self._config.get("meal_types", ["lunch", "dinner"])

    @property
    def telegram(self) -> dict:
        """Get Telegram configuration."""
        return self._config.get("telegram", {})


class MenuAnalyzer:
    """Analyzer for dining hall menus."""

    def __init__(self, config: Config | None = None):
        """Initialize analyzer with optional config."""
        self.config = config or Config()
        self.storage = get_storage()

    def _is_always_available(self, item_name: str) -> bool:
        """Check if an item is always available (should be filtered)."""
        item_lower = item_name.lower()
        for pattern in self.config.always_available:
            if pattern.lower() in item_lower:
                return True
        return False

    def score_dining_hall(
        self,
        menu: DailyMenu,
        meal_type: str = "lunch",
    ) -> DiningHallScore:
        """Score a dining hall's menu for a specific meal.

        Scoring rules (10-point scale, half-star increments):
        - Score 1: Neutral, doesn't affect ranking
        - Score 2-10: Positive, counts toward ranking

        Rankings: first by count of 10s, then 9s, then 8s, etc.
        """
        meal = menu.meals.get(meal_type)
        if not meal:
            return DiningHallScore(
                dining_hall=menu.dining_hall,
                total_score=0,
                meal_type=meal_type,
            )

        positive_count = 0  # Items rated 2-10
        score_counts: dict[int, int] = {i: 0 for i in range(2, 11)}  # 2-10
        favorite_items = []  # 8-10 (4-5 stars)
        good_items = []  # 4-7 (2-3.5 stars)
        low_items = []  # 2-3 (1-1.5 stars)

        ratings = self.storage.get_ratings_dict()

        for item in meal.items:
            if self._is_always_available(item.name):
                continue

            rating = ratings.get(item.name, 0)

            # Only count items rated 2-10 (not unrated or rated 1)
            if rating >= 2:
                positive_count += 1
                score_counts[rating] = score_counts.get(rating, 0) + 1

                if rating >= 8:  # 4-5 stars
                    favorite_items.append(item.name)
                elif rating >= 4:  # 2-3.5 stars
                    good_items.append(item.name)
                else:  # 2-3 (1-1.5 stars)
                    low_items.append(item.name)

        return DiningHallScore(
            dining_hall=menu.dining_hall,
            total_score=positive_count,
            score_counts=score_counts,
            favorite_items=favorite_items,
            good_items=good_items,
            low_items=low_items,
            meal_type=meal_type,
        )

    def _get_sort_key(self, score: DiningHallScore) -> tuple:
        """Generate sort key: first by 10s count, then 9s, then 8s, etc."""
        # Returns tuple like (count_of_10, count_of_9, count_of_8, ..., count_of_2)
        return tuple(score.score_counts.get(i, 0) for i in range(10, 1, -1))

    def analyze_day(
        self,
        menu_day: MenuDay,
        meal_type: str = "lunch",
    ) -> DailyRecommendation:
        """Analyze all dining halls for a day and return recommendations."""
        scores = []

        for daily_menu in menu_day.menus:
            score = self.score_dining_hall(daily_menu, meal_type)
            scores.append(score)

        # Sort by: first count of 10s, then 9s, then 8s, etc. (all descending)
        scores.sort(key=self._get_sort_key, reverse=True)

        top_pick = scores[0] if scores else None

        return DailyRecommendation(
            date=menu_day.date,
            meal_type=meal_type,
            rankings=scores,
            top_pick=top_pick,
        )

    def _clean_item_name(self, item_name: str) -> str:
        """Clean item name by removing redundant suffixes and prefixes."""
        # Remove trailing " - XxxXxx" suffix (dining hall name)
        name = re.sub(r"\s+-\s+\S+.*$", "", item_name)
        # Remove "Build Your Own " prefix
        name = re.sub(r"^Build Your Own\s+", "", name)
        return name.strip()

    def format_recommendation(self, rec: DailyRecommendation) -> str:
        """Format a recommendation for Telegram Markdown display."""
        from datetime import datetime
        weekday = datetime.strptime(rec.date, "%Y-%m-%d").strftime("%A")

        lines = [f"📅 *{rec.date} ({weekday}) - {rec.meal_type.capitalize()}*"]

        medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣", "6️⃣"]

        for i, score in enumerate(rec.rankings):
            medal = medals[i] if i < len(medals) else f"{i+1}."
            hall_name = score.dining_hall.name
            has_recommended = score.favorite_items or score.good_items

            if has_recommended:
                # Expanded format for halls with recommendations
                lines.append("")  # blank line before
                top_label = " (🔥 Top Choice)" if i == 0 else ""
                lines.append(f"{medal} *{hall_name}*{top_label}")

                if score.favorite_items:
                    cleaned = [self._clean_item_name(n) for n in score.favorite_items[:2]]
                    lines.append(f"🌟 推荐: {', '.join(cleaned)}")
                elif score.good_items:
                    cleaned = [self._clean_item_name(n) for n in score.good_items[:2]]
                    lines.append(f"👍 推荐: {', '.join(cleaned)}")

                if score.low_items:
                    cleaned = [self._clean_item_name(n) for n in score.low_items[:2]]
                    lines.append(f"⚠️ 避雷: {', '.join(cleaned)}")
            else:
                # Compact format for halls with no recommendations
                lines.append(f"{medal} {hall_name}: ❌ 无推荐菜")

        lines.append("")
        lines.append("[📋 查看今日完整菜单](https://what-should-i-eat-today-production.up.railway.app/menu)")

        return "\n".join(lines)

    def format_menu(self, menu: DailyMenu, meal_type: str = "lunch") -> str:
        """Format a dining hall menu for display."""
        meal = menu.meals.get(meal_type)
        if not meal:
            return f"No {meal_type} menu available for {menu.dining_hall.name}"

        # Add weekday to date
        from datetime import datetime
        weekday = datetime.strptime(menu.date, "%Y-%m-%d").strftime("%A")

        lines = [
            f"🍽️ {menu.dining_hall.name} - {meal_type.capitalize()}",
            f"📅 {menu.date} ({weekday})",
            "",
        ]

        ratings = self.storage.get_ratings_dict()

        for item in meal.items:
            if self._is_always_available(item.name):
                continue

            rating = ratings.get(item.name, 0)

            # Show stars for rated items (rating / 2 = star count)
            if rating >= 8:
                indicator = "⭐"
            elif rating >= 2:
                stars = rating / 2
                full = int(stars)
                half = "½" if stars % 1 else ""
                indicator = f"{'★' * full}{half}"
            else:
                indicator = "•"

            line = f"{indicator} {item.name}"

            if item.icons:
                icons_str = ", ".join(item.icons[:3])
                line += f" [{icons_str}]"

            lines.append(line)

        return "\n".join(lines)


# Global analyzer instance
_analyzer: MenuAnalyzer | None = None


def get_analyzer() -> MenuAnalyzer:
    """Get the global analyzer instance."""
    global _analyzer
    if _analyzer is None:
        _analyzer = MenuAnalyzer()
    return _analyzer
