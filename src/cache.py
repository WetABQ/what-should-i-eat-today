"""Menu caching system using a single Parquet file."""

from datetime import date, timedelta
from pathlib import Path

import polars as pl

from .models import DailyMenu, DiningHall, MealPeriod, MenuItem, NutritionInfo

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_FILE = CACHE_DIR / "menus.parquet"

# Schema for cached menu items
MENU_SCHEMA = {
    "date": pl.Utf8,
    "hall_id": pl.Int64,
    "hall_name": pl.Utf8,
    "hall_slug": pl.Utf8,
    "meal_type": pl.Utf8,
    "item_id": pl.Int64,
    "item_name": pl.Utf8,
    "food_category": pl.Utf8,
    "icons": pl.List(pl.Utf8),
    "station_id": pl.Int64,
    "station_name": pl.Utf8,
    "calories": pl.Float64,
    "protein": pl.Float64,
    "carbohydrates": pl.Float64,
    "fat": pl.Float64,
    "fiber": pl.Float64,
    "sodium": pl.Float64,
}


def _ensure_cache_dir() -> None:
    """Ensure the cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _is_cacheable_date(menu_date: date) -> bool:
    """Check if the date should be cached (within ±7 days from today)."""
    today = date.today()
    delta = abs((menu_date - today).days)
    return delta <= 7


def _load_cache() -> pl.DataFrame:
    """Load the cache file."""
    if not CACHE_FILE.exists():
        return pl.DataFrame(schema=MENU_SCHEMA)
    try:
        return pl.read_parquet(CACHE_FILE)
    except Exception:
        return pl.DataFrame(schema=MENU_SCHEMA)


def _save_cache(df: pl.DataFrame) -> None:
    """Save the cache file."""
    _ensure_cache_dir()
    df.write_parquet(CACHE_FILE)


def get_cached_menu(menu_date: date, hall_slug: str) -> DailyMenu | None:
    """Get a cached menu if it exists."""
    df = _load_cache()
    if df.height == 0:
        return None

    date_str = menu_date.isoformat()
    filtered = df.filter(
        (pl.col("date") == date_str) & (pl.col("hall_slug") == hall_slug)
    )

    if filtered.height == 0:
        return None

    # Get hall info from first row
    first_row = filtered.row(0, named=True)
    dining_hall = DiningHall(
        id=first_row["hall_id"],
        name=first_row["hall_name"],
        slug=first_row["hall_slug"],
        active=True,
    )

    # Filter out placeholder rows (item_id = 0 means empty menu marker)
    real_items = filtered.filter(pl.col("item_id") != 0)

    # Group items by meal type
    meals = {}
    for meal_type in real_items["meal_type"].unique().to_list():
        meal_df = real_items.filter(pl.col("meal_type") == meal_type)
        items = []
        for row in meal_df.iter_rows(named=True):
            nutrition = None
            if any([row["calories"], row["protein"], row["carbohydrates"],
                    row["fat"], row["fiber"], row["sodium"]]):
                nutrition = NutritionInfo(
                    calories=row["calories"],
                    protein=row["protein"],
                    carbohydrates=row["carbohydrates"],
                    fat=row["fat"],
                    fiber=row["fiber"],
                    sodium=row["sodium"],
                )
            items.append(MenuItem(
                id=row["item_id"],
                name=row["item_name"],
                food_category=row["food_category"],
                icons=row["icons"] or [],
                station_id=row["station_id"],
                station_name=row["station_name"],
                nutrition_info=nutrition,
            ))
        meals[meal_type] = MealPeriod(name=meal_type.capitalize(), items=items)

    return DailyMenu(
        dining_hall=dining_hall,
        date=date_str,
        meals=meals,
    )


def set_cached_menu(menu: DailyMenu) -> None:
    """Cache a menu (within ±7 days from today)."""
    menu_date = date.fromisoformat(menu.date)
    if not _is_cacheable_date(menu_date):
        return

    # Build rows for this menu
    rows = []
    for meal_type, meal in menu.meals.items():
        for item in meal.items:
            nutrition = item.nutrition_info
            rows.append({
                "date": menu.date,
                "hall_id": menu.dining_hall.id,
                "hall_name": menu.dining_hall.name,
                "hall_slug": menu.dining_hall.slug,
                "meal_type": meal_type,
                "item_id": item.id,
                "item_name": item.name,
                "food_category": item.food_category,
                "icons": item.icons,
                "station_id": item.station_id,
                "station_name": item.station_name,
                "calories": nutrition.calories if nutrition else None,
                "protein": nutrition.protein if nutrition else None,
                "carbohydrates": nutrition.carbohydrates if nutrition else None,
                "fat": nutrition.fat if nutrition else None,
                "fiber": nutrition.fiber if nutrition else None,
                "sodium": nutrition.sodium if nutrition else None,
            })

    # If no items, add a placeholder row to mark this date/hall as checked
    if not rows:
        rows.append({
            "date": menu.date,
            "hall_id": menu.dining_hall.id,
            "hall_name": menu.dining_hall.name,
            "hall_slug": menu.dining_hall.slug,
            "meal_type": "__empty__",
            "item_id": 0,  # Marker for empty menu
            "item_name": "",
            "food_category": None,
            "icons": [],
            "station_id": None,
            "station_name": None,
            "calories": None,
            "protein": None,
            "carbohydrates": None,
            "fat": None,
            "fiber": None,
            "sodium": None,
        })

    new_df = pl.DataFrame(rows, schema=MENU_SCHEMA)

    # Load existing cache and remove old entries for this date/hall
    existing = _load_cache()
    if existing.height > 0:
        existing = existing.filter(
            ~((pl.col("date") == menu.date) & (pl.col("hall_slug") == menu.dining_hall.slug))
        )
        combined = pl.concat([existing, new_df])
    else:
        combined = new_df

    _save_cache(combined)


def clear_cache(menu_date: date | None = None, hall_slug: str | None = None) -> int:
    """Clear cache for a specific date/hall or all cache.

    Returns the number of rows deleted.
    """
    df = _load_cache()
    if df.height == 0:
        return 0

    original_count = df.height

    if menu_date and hall_slug:
        df = df.filter(
            ~((pl.col("date") == menu_date.isoformat()) & (pl.col("hall_slug") == hall_slug))
        )
    elif menu_date:
        df = df.filter(pl.col("date") != menu_date.isoformat())
    elif hall_slug:
        df = df.filter(pl.col("hall_slug") != hall_slug)
    else:
        # Clear all
        df = pl.DataFrame(schema=MENU_SCHEMA)

    deleted = original_count - df.height
    _save_cache(df)
    return deleted


def get_cache_status() -> dict:
    """Get information about the current cache state."""
    df = _load_cache()
    if df.height == 0:
        return {"total_items": 0, "dates": [], "halls": [], "summary": []}

    # Get unique date/hall combinations with item counts
    summary = (
        df.group_by(["date", "hall_slug"])
        .agg(pl.count().alias("item_count"))
        .sort(["date", "hall_slug"])
    )

    return {
        "total_items": df.height,
        "dates": sorted(df["date"].unique().to_list()),
        "halls": sorted(df["hall_slug"].unique().to_list()),
        "summary": summary.to_dicts(),
    }


def get_all_cached_menus() -> pl.DataFrame:
    """Get the full cache DataFrame for analysis."""
    return _load_cache()
