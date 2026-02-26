"""FastAPI backend for the dining hall menu system."""

from datetime import date
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from .analyzer import get_analyzer
from .cache import clear_cache, get_cache_status
from .models import DailyRecommendation, FoodRating
from .scraper import (
    fetch_all_menus,
    fetch_daily_menu,
    get_active_dining_halls,
    get_dining_hall_by_slug,
)
from .storage import get_storage

app = FastAPI(
    title="What Should I Eat Today",
    description="UW-Madison Dining Hall Menu Analyzer API",
    version="1.0.0",
)

# CORS middleware for Vue frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Request/Response Models ===


class RatingRequest(BaseModel):
    """Request body for creating/updating a rating."""

    food_name: str
    score: int = Field(ge=1, le=10)  # 1-10, displayed as 0.5-5 stars
    dining_hall: str | None = None


class DiningHallResponse(BaseModel):
    """Response for a dining hall."""

    id: int
    name: str
    slug: str
    active: bool


class MenuItemResponse(BaseModel):
    """Response for a menu item."""

    id: int
    name: str
    food_category: str | None
    icons: list[str]
    rating: int = 0  # User's star rating (0 = unrated, 1-5 = rated)


class MealResponse(BaseModel):
    """Response for a meal period."""

    name: str
    items: list[MenuItemResponse]


class DailyMenuResponse(BaseModel):
    """Response for a dining hall's daily menu."""

    dining_hall: DiningHallResponse
    date: str
    meals: dict[str, MealResponse]


# === Endpoints ===


@app.get("/api/dining-halls", response_model=list[DiningHallResponse])
async def get_dining_halls():
    """Get list of active dining halls."""
    halls = get_active_dining_halls()
    return [
        DiningHallResponse(
            id=h.id,
            name=h.name,
            slug=h.slug,
            active=h.active,
        )
        for h in halls
    ]


@app.get("/api/menu/{hall}/{menu_date}")
async def get_menu(
    hall: str,
    menu_date: str,
    meal_type: Annotated[str, Query()] = "lunch",
) -> DailyMenuResponse:
    """Get menu for a specific dining hall and date."""
    dining_hall = get_dining_hall_by_slug(hall)
    if not dining_hall:
        raise HTTPException(status_code=404, detail=f"Dining hall not found: {hall}")

    try:
        parsed_date = date.fromisoformat(menu_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    daily_menu = await fetch_daily_menu(dining_hall, parsed_date, [meal_type])

    analyzer = get_analyzer()
    storage = get_storage()
    ratings = storage.get_ratings_dict()
    meals_response = {}

    for meal_name, meal in daily_menu.meals.items():
        items_response = []
        for item in meal.items:
            if analyzer._is_always_available(item.name):
                continue

            items_response.append(
                MenuItemResponse(
                    id=item.id,
                    name=item.name,
                    food_category=item.food_category,
                    icons=item.icons,
                    rating=ratings.get(item.name, 0),
                )
            )

        meals_response[meal_name] = MealResponse(
            name=meal.name,
            items=items_response,
        )

    return DailyMenuResponse(
        dining_hall=DiningHallResponse(
            id=dining_hall.id,
            name=dining_hall.name,
            slug=dining_hall.slug,
            active=dining_hall.active,
        ),
        date=daily_menu.date,
        meals=meals_response,
    )


@app.get("/api/recommend/{menu_date}")
async def get_recommendation(
    menu_date: str,
    meal_type: Annotated[str, Query()] = "lunch",
) -> DailyRecommendation:
    """Get dining hall recommendations using server-side ratings."""
    try:
        parsed_date = date.fromisoformat(menu_date)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")

    menu_day = await fetch_all_menus(parsed_date, [meal_type])
    analyzer = get_analyzer()

    return analyzer.analyze_day(menu_day, meal_type)


# === Ratings Endpoints ===


@app.get("/api/ratings")
async def get_ratings() -> list[FoodRating]:
    """Get all food ratings."""
    storage = get_storage()
    return storage.load_ratings()


@app.post("/api/ratings")
async def create_rating(request: RatingRequest) -> FoodRating:
    """Create or update a food rating."""
    storage = get_storage()
    rating = storage.save_rating(
        food_name=request.food_name,
        score=request.score,
        dining_hall=request.dining_hall,
    )
    return rating


@app.delete("/api/ratings/{food_name}")
async def delete_rating(food_name: str):
    """Delete a food rating."""
    storage = get_storage()
    if storage.delete_rating(food_name):
        return {"status": "deleted"}
    raise HTTPException(status_code=404, detail="Rating not found")


# === Import/Export Endpoints ===


@app.get("/api/export")
async def export_data():
    """Export all ratings for backup."""
    storage = get_storage()
    return {
        "ratings": storage._load_ratings_raw(),
    }


@app.post("/api/import")
async def import_data(data: dict):
    """Import ratings from backup, replacing all existing ratings."""
    storage = get_storage()
    ratings = data.get("ratings", [])
    if ratings:
        storage._save_ratings_raw(ratings)
    return {"status": "imported", "count": len(ratings)}


# === Cache Endpoints ===


@app.get("/api/cache/status")
async def cache_status():
    """Get cache status information."""
    return get_cache_status()


@app.post("/api/cache/refresh")
async def refresh_cache(
    menu_date: Annotated[str | None, Query()] = None,
    hall: Annotated[str | None, Query()] = None,
):
    """Refresh (clear) cache and re-fetch menus.

    If menu_date and/or hall are provided, only refresh that specific cache.
    Otherwise, refresh all cache for today.
    """
    # Parse date if provided
    parsed_date = None
    if menu_date:
        try:
            parsed_date = date.fromisoformat(menu_date)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    else:
        parsed_date = date.today()

    # Clear the cache
    deleted = clear_cache(parsed_date, hall)

    # Re-fetch the data
    if hall:
        dining_hall = get_dining_hall_by_slug(hall)
        if not dining_hall:
            raise HTTPException(status_code=404, detail=f"Dining hall not found: {hall}")
        await fetch_daily_menu(dining_hall, parsed_date, use_cache=False)
    else:
        await fetch_all_menus(parsed_date, use_cache=False)

    return {
        "status": "refreshed",
        "deleted_cache_files": deleted,
        "date": parsed_date.isoformat(),
        "hall": hall,
    }


# === Health Check ===


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


# === Static Files (Vue Frontend) ===

# Serve Vue frontend in production
STATIC_DIR = Path(__file__).parent.parent / "web" / "dist"

if STATIC_DIR.exists():
    # Serve static assets
    app.mount("/assets", StaticFiles(directory=STATIC_DIR / "assets"), name="assets")

    # Serve index.html for all non-API routes (SPA fallback)
    @app.get("/{full_path:path}")
    async def serve_spa(full_path: str):
        """Serve the Vue SPA for all non-API routes."""
        # Don't interfere with API routes
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not found")

        index_path = STATIC_DIR / "index.html"
        if index_path.exists():
            return FileResponse(index_path)
        raise HTTPException(status_code=404, detail="Frontend not built")
