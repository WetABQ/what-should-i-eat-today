"""Menu caching system using a single Parquet file."""

from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl

from .models import DailyMenu, DiningHall, MealPeriod, MenuItem, NutritionInfo

CACHE_DIR = Path(__file__).parent.parent / "data" / "cache"
CACHE_FILE = CACHE_DIR / "menus.parquet"
CHICAGO_TZ = ZoneInfo("America/Chicago")

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
    "cached_at": pl.Utf8,  # ISO timestamp when cached
}


def _ensure_cache_dir() -> None:
    """Ensure the cache directory exists."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _now_cst() -> datetime:
    """Get current time in Chicago timezone."""
    return datetime.now(CHICAGO_TZ)


def _load_cache() -> pl.DataFrame:
    """Load the cache file."""
    if not CACHE_FILE.exists():
        return pl.DataFrame(schema=MENU_SCHEMA)
    try:
        df = pl.read_parquet(CACHE_FILE)
        # Add cached_at column if missing (for migration)
        if "cached_at" not in df.columns:
            df = df.with_columns(pl.lit(None).alias("cached_at"))
        return df
    except Exception:
        return pl.DataFrame(schema=MENU_SCHEMA)


def _save_cache(df: pl.DataFrame) -> None:
    """Save the cache file."""
    _ensure_cache_dir()
    df.write_parquet(CACHE_FILE)


def _is_cache_valid(cached_at: str | None, menu_date: date) -> bool:
    """Check if cache entry is still valid.

    Rules:
    - Cache for today expires after 2 hours (menus might update)
    - Cache for future dates expires after 6 hours
    - Cache for past dates never expires (historical data)
    """
    if not cached_at:
        return True  # Old cache without timestamp, assume valid

    try:
        cached_time = datetime.fromisoformat(cached_at)
        now = _now_cst()
        today = now.date()

        age = now - cached_time.replace(tzinfo=CHICAGO_TZ)

        if menu_date == today:
            # Today's cache expires after 2 hours
            return age < timedelta(hours=2)
        elif menu_date > today:
            # Future cache expires after 6 hours
            return age < timedelta(hours=6)
        else:
            # Past cache doesn't expire
            return True
    except Exception:
        return True


def get_cached_menu(
    menu_date: date,
    hall_slug: str,
    meal_type: str,
) -> MealPeriod | None:
    """Get a cached meal if it exists and is valid.

    Returns MealPeriod for the specific meal_type, or None if not cached.
    """
    df = _load_cache()
    if df.height == 0:
        return None

    date_str = menu_date.isoformat()
    filtered = df.filter(
        (pl.col("date") == date_str) &
        (pl.col("hall_slug") == hall_slug) &
        (pl.col("meal_type") == meal_type)
    )

    if filtered.height == 0:
        return None

    # Check cache validity
    first_row = filtered.row(0, named=True)
    if not _is_cache_valid(first_row.get("cached_at"), menu_date):
        return None

    # Filter out placeholder rows (item_id = 0 means empty menu marker)
    real_items = filtered.filter(pl.col("item_id") != 0)

    # Build items list
    items = []
    for row in real_items.iter_rows(named=True):
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

    return MealPeriod(name=meal_type.capitalize(), items=items)


def get_cached_daily_menu(
    menu_date: date,
    hall_slug: str,
    hall: DiningHall,
) -> DailyMenu | None:
    """Get a fully cached daily menu (all meal types)."""
    df = _load_cache()
    if df.height == 0:
        return None

    date_str = menu_date.isoformat()
    filtered = df.filter(
        (pl.col("date") == date_str) &
        (pl.col("hall_slug") == hall_slug)
    )

    if filtered.height == 0:
        return None

    # Get all meal types from cache
    meal_types = filtered["meal_type"].unique().to_list()

    meals = {}
    for meal_type in meal_types:
        if meal_type == "__empty__":
            continue
        meal = get_cached_menu(menu_date, hall_slug, meal_type)
        if meal is not None:
            meals[meal_type] = meal

    if not meals:
        return None

    return DailyMenu(
        dining_hall=hall,
        date=date_str,
        meals=meals,
    )


def set_cached_meal(
    menu_date: date,
    hall: DiningHall,
    meal_type: str,
    items: list[MenuItem],
) -> None:
    """Cache a single meal period."""
    date_str = menu_date.isoformat()
    cached_at = _now_cst().isoformat()

    # Build rows
    rows = []
    for item in items:
        nutrition = item.nutrition_info
        rows.append({
            "date": date_str,
            "hall_id": hall.id,
            "hall_name": hall.name,
            "hall_slug": hall.slug,
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
            "cached_at": cached_at,
        })

    # Don't cache empty meals - let them be re-fetched
    # This prevents permanently caching "no menu available" states
    if not rows:
        return

    new_df = pl.DataFrame(rows, schema=MENU_SCHEMA)

    # Load existing cache and remove old entries for this date/hall/meal
    existing = _load_cache()
    if existing.height > 0:
        existing = existing.filter(
            ~(
                (pl.col("date") == date_str) &
                (pl.col("hall_slug") == hall.slug) &
                (pl.col("meal_type") == meal_type)
            )
        )
        combined = pl.concat([existing, new_df])
    else:
        combined = new_df

    _save_cache(combined)


def set_cached_menu(menu: DailyMenu) -> None:
    """Cache a daily menu (all meal types)."""
    menu_date = date.fromisoformat(menu.date)

    for meal_type, meal in menu.meals.items():
        set_cached_meal(menu_date, menu.dining_hall, meal_type, meal.items)


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

    # Get unique date/hall/meal combinations with item counts
    summary = (
        df.filter(pl.col("item_id") != 0)  # Exclude placeholder rows
        .group_by(["date", "hall_slug", "meal_type"])
        .agg(pl.count().alias("item_count"))
        .sort(["date", "hall_slug", "meal_type"])
    )

    return {
        "total_items": df.filter(pl.col("item_id") != 0).height,
        "dates": sorted(df["date"].unique().to_list()),
        "halls": sorted(df["hall_slug"].unique().to_list()),
        "summary": summary.to_dicts(),
    }


def get_all_cached_menus() -> pl.DataFrame:
    """Get the full cache DataFrame for analysis."""
    return _load_cache()
