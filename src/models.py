"""Data models for the dining hall menu system."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class NutritionInfo(BaseModel):
    """Nutritional information for a menu item."""

    calories: float | None = None
    protein: float | None = None
    carbohydrates: float | None = None
    fat: float | None = None
    fiber: float | None = None
    sodium: float | None = None


class MenuItem(BaseModel):
    """A single menu item from a dining hall."""

    id: int
    name: str
    food_category: str | None = None
    icons: list[str] = Field(default_factory=list)
    nutrition_info: NutritionInfo | None = None
    station_id: int | None = None
    station_name: str | None = None

    @classmethod
    def from_api_response(cls, data: dict[str, Any]) -> "MenuItem":
        """Create a MenuItem from the Nutrislice API response."""
        icons = []
        icons_data = data.get("icons")
        if icons_data:
            # Handle nested structure: {"food_icons": [...], "myplate_icons": [...]}
            if isinstance(icons_data, dict):
                for icon_list in icons_data.values():
                    if isinstance(icon_list, list):
                        for icon in icon_list:
                            if isinstance(icon, dict) and icon.get("name"):
                                icons.append(icon["name"])
            # Handle flat list of icons
            elif isinstance(icons_data, list):
                for icon in icons_data:
                    if isinstance(icon, dict) and icon.get("name"):
                        icons.append(icon["name"])
                    elif isinstance(icon, str) and icon:
                        icons.append(icon)

        nutrition = None
        if data.get("rounded_nutrition_info"):
            info = data["rounded_nutrition_info"]
            nutrition = NutritionInfo(
                calories=info.get("calories"),
                protein=info.get("protein"),
                carbohydrates=info.get("carbs"),
                fat=info.get("total_fat"),
                fiber=info.get("dietary_fiber"),
                sodium=info.get("sodium"),
            )

        return cls(
            id=data.get("id", 0),
            name=data.get("name", "Unknown"),
            food_category=data.get("food_category"),
            icons=icons,
            nutrition_info=nutrition,
            station_id=data.get("station_id"),
        )


class MealPeriod(BaseModel):
    """A meal period (breakfast, lunch, dinner) with its menu items."""

    name: str
    items: list[MenuItem] = Field(default_factory=list)


class DiningHall(BaseModel):
    """A dining hall with its basic information."""

    id: int
    name: str
    slug: str
    active: bool = True


class DailyMenu(BaseModel):
    """Menu for a specific dining hall on a specific date."""

    dining_hall: DiningHall
    date: str  # YYYY-MM-DD format
    meals: dict[str, MealPeriod] = Field(default_factory=dict)  # meal_type -> MealPeriod


class MenuDay(BaseModel):
    """All menus for all dining halls on a specific date."""

    date: str  # YYYY-MM-DD format
    menus: list[DailyMenu] = Field(default_factory=list)


class FoodRating(BaseModel):
    """User rating for a specific food item."""

    food_name: str
    score: int = Field(ge=1, le=10)  # 1-10, displayed as 0.5-5 stars
    dining_hall: str | None = None
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class DiningHallScore(BaseModel):
    """Score calculation result for a dining hall."""

    dining_hall: DiningHall
    total_score: int  # Count of items rated 2-10
    score_counts: dict[int, int] = Field(default_factory=dict)  # score -> count (for ranking)
    favorite_items: list[str] = Field(default_factory=list)  # 8-10 score items (4-5 stars)
    good_items: list[str] = Field(default_factory=list)  # 4-7 score items (2-3.5 stars)
    low_items: list[str] = Field(default_factory=list)  # 2-3 score items (1-1.5 stars)
    meal_type: str = "lunch"


class DailyRecommendation(BaseModel):
    """Daily recommendation result."""

    date: str
    meal_type: str
    rankings: list[DiningHallScore] = Field(default_factory=list)
    top_pick: DiningHallScore | None = None
