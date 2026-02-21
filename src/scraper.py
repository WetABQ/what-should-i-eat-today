"""Nutrislice API scraper for UW-Madison dining halls."""

import asyncio
from datetime import date, datetime

import httpx

from .cache import clear_cache, get_cached_menu, set_cached_menu
from .models import DailyMenu, DiningHall, MealPeriod, MenuItem, MenuDay

BASE_URL = "https://wisc-housingdining.api.nutrislice.com/menu/api"

# Known dining halls with their slugs
DINING_HALLS = [
    DiningHall(id=1, name="Carson's Market", slug="carsons-market", active=False),
    DiningHall(id=2, name="Four Lakes Market", slug="four-lakes-market", active=True),
    DiningHall(id=3, name="Gordon Avenue Market", slug="gordon-avenue-market", active=True),
    DiningHall(id=4, name="Liz's Market", slug="lizs-market", active=True),
    DiningHall(id=5, name="Lowell Market", slug="lowell-market", active=True),
    DiningHall(id=6, name="Rheta's Market", slug="rhetas-market", active=True),
]

# Menu types to fetch
MENU_TYPES = ["breakfast", "lunch", "dinner"]


async def fetch_schools(client: httpx.AsyncClient | None = None) -> list[DiningHall]:
    """Fetch list of available schools/dining halls from the API."""
    should_close = client is None
    if client is None:
        client = httpx.AsyncClient()

    try:
        response = await client.get(f"{BASE_URL}/schools/?format=json")
        response.raise_for_status()
        data = response.json()

        halls = []
        for school in data:
            halls.append(
                DiningHall(
                    id=school.get("id", 0),
                    name=school.get("name", "Unknown"),
                    slug=school.get("slug", ""),
                    active=school.get("active", True),
                )
            )
        return halls
    finally:
        if should_close:
            await client.aclose()


async def fetch_menu(
    school_slug: str,
    menu_date: date | None = None,
    menu_type: str = "lunch",
    client: httpx.AsyncClient | None = None,
) -> list[MenuItem]:
    """Fetch menu for a specific dining hall, date, and meal type."""
    if menu_date is None:
        menu_date = date.today()

    should_close = client is None
    if client is None:
        client = httpx.AsyncClient()

    try:
        url = (
            f"{BASE_URL}/weeks/school/{school_slug}/menu-type/{menu_type}/"
            f"{menu_date.year}/{menu_date.month}/{menu_date.day}/?format=json"
        )
        response = await client.get(url)
        response.raise_for_status()
        data = response.json()

        items = []
        # Parse the week data to find the specific day
        date_str = menu_date.strftime("%Y-%m-%d")

        for day_data in data.get("days", []):
            if day_data.get("date") == date_str:
                for menu_item in day_data.get("menu_items", []):
                    if menu_item.get("food"):
                        food = menu_item["food"]
                        food["station_id"] = menu_item.get("station_id")
                        items.append(MenuItem.from_api_response(food))
                break

        return items
    except httpx.HTTPStatusError:
        return []
    finally:
        if should_close:
            await client.aclose()


async def fetch_daily_menu(
    hall: DiningHall,
    menu_date: date | None = None,
    menu_types: list[str] | None = None,
    client: httpx.AsyncClient | None = None,
    use_cache: bool = True,
) -> DailyMenu:
    """Fetch all meals for a dining hall on a specific date.

    Args:
        hall: The dining hall to fetch the menu for.
        menu_date: The date to fetch the menu for. Defaults to today.
        menu_types: List of meal types to fetch. Defaults to all types.
        client: Optional httpx client to reuse.
        use_cache: Whether to use cached data if available.
    """
    if menu_date is None:
        menu_date = date.today()
    if menu_types is None:
        menu_types = MENU_TYPES

    # Try to get from cache first
    if use_cache:
        cached = get_cached_menu(menu_date, hall.slug)
        if cached:
            # Filter meals to only requested types
            if menu_types != MENU_TYPES:
                cached.meals = {k: v for k, v in cached.meals.items() if k in menu_types}
            return cached

    should_close = client is None
    if client is None:
        client = httpx.AsyncClient()

    try:
        meals = {}
        tasks = [
            fetch_menu(hall.slug, menu_date, meal_type, client)
            for meal_type in menu_types
        ]
        results = await asyncio.gather(*tasks)

        for meal_type, items in zip(menu_types, results):
            if items:
                meals[meal_type] = MealPeriod(name=meal_type.capitalize(), items=items)

        daily_menu = DailyMenu(
            dining_hall=hall,
            date=menu_date.strftime("%Y-%m-%d"),
            meals=meals,
        )

        # Cache the result (only for today/tomorrow)
        set_cached_menu(daily_menu)

        return daily_menu
    finally:
        if should_close:
            await client.aclose()


async def fetch_all_menus(
    menu_date: date | None = None,
    menu_types: list[str] | None = None,
    halls: list[DiningHall] | None = None,
    use_cache: bool = True,
) -> MenuDay:
    """Fetch menus for all active dining halls on a specific date.

    Args:
        menu_date: The date to fetch menus for. Defaults to today.
        menu_types: List of meal types to fetch.
        halls: List of dining halls to fetch. Defaults to all active halls.
        use_cache: Whether to use cached data if available.
    """
    if menu_date is None:
        menu_date = date.today()
    if halls is None:
        halls = [h for h in DINING_HALLS if h.active]

    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_daily_menu(hall, menu_date, menu_types, client, use_cache)
            for hall in halls
        ]
        daily_menus = await asyncio.gather(*tasks)

        return MenuDay(
            date=menu_date.strftime("%Y-%m-%d"),
            menus=list(daily_menus),
        )


def get_active_dining_halls() -> list[DiningHall]:
    """Get list of active dining halls."""
    return [h for h in DINING_HALLS if h.active]


def get_dining_hall_by_slug(slug: str) -> DiningHall | None:
    """Get a dining hall by its slug."""
    for hall in DINING_HALLS:
        if hall.slug == slug:
            return hall
    return None


# Synchronous wrapper for CLI usage
def fetch_all_menus_sync(
    menu_date: date | None = None,
    menu_types: list[str] | None = None,
) -> MenuDay:
    """Synchronous wrapper for fetch_all_menus."""
    return asyncio.run(fetch_all_menus(menu_date, menu_types))


def fetch_menu_sync(
    school_slug: str,
    menu_date: date | None = None,
    menu_type: str = "lunch",
) -> list[MenuItem]:
    """Synchronous wrapper for fetch_menu."""
    return asyncio.run(fetch_menu(school_slug, menu_date, menu_type))
