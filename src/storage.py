"""JSON-based storage for ratings."""

import json
from datetime import datetime
from pathlib import Path

from .models import FoodRating

DATA_DIR = Path(__file__).parent.parent / "data"
DEFAULT_RATINGS_FILE = DATA_DIR / "presets" / "default.json"


class Storage:
    """Storage class for managing ratings in JSON files."""

    def __init__(self, data_dir: Path | None = None):
        """Initialize storage with optional custom data directory."""
        self.data_dir = data_dir or DATA_DIR
        self.ratings_file = self.data_dir / "ratings.json"
        self._ensure_data_dir()
        self._load_default_ratings_if_needed()

    def _ensure_data_dir(self) -> None:
        """Ensure the data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    def _load_default_ratings_if_needed(self) -> None:
        """Load default ratings if no ratings exist."""
        if self.ratings_file.exists():
            try:
                with open(self.ratings_file) as f:
                    ratings = json.load(f)
                if ratings:
                    return
            except json.JSONDecodeError:
                pass

        if DEFAULT_RATINGS_FILE.exists():
            try:
                with open(DEFAULT_RATINGS_FILE) as f:
                    data = json.load(f)
                ratings = data if isinstance(data, list) else data.get("ratings", [])
                if ratings:
                    self._save_ratings_raw(ratings)
                    print(f"Loaded {len(ratings)} default ratings")
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Failed to load default ratings: {e}")

    # === Ratings ===

    def _load_ratings_raw(self) -> list[dict]:
        """Load ratings from JSON file (always fresh read)."""
        if not self.ratings_file.exists():
            return []

        try:
            with open(self.ratings_file) as f:
                data = json.load(f)
            # Support both plain list and {"ratings": [...]} format
            if isinstance(data, dict):
                return data.get("ratings", [])
            return data
        except json.JSONDecodeError:
            return []

    def _save_ratings_raw(self, ratings: list[dict]) -> None:
        """Save ratings to JSON file."""
        with open(self.ratings_file, "w") as f:
            json.dump(ratings, f, indent=2)

    def load_ratings(self) -> list[FoodRating]:
        """Load all ratings."""
        raw = self._load_ratings_raw()
        ratings = []
        for r in raw:
            ratings.append(FoodRating(
                food_name=r["food_name"],
                score=r["score"],
                dining_hall=r.get("dining_hall"),
                created_at=datetime.fromisoformat(r["created_at"]) if r.get("created_at") else datetime.now(),
                updated_at=datetime.fromisoformat(r["updated_at"]) if r.get("updated_at") else datetime.now(),
            ))
        return ratings

    def save_rating(
        self,
        food_name: str,
        score: int,
        dining_hall: str | None = None,
    ) -> FoodRating:
        """Save or update a food rating."""
        now = datetime.now()
        ratings = self._load_ratings_raw()

        existing_idx = None
        for i, r in enumerate(ratings):
            if r["food_name"] == food_name:
                existing_idx = i
                break

        if existing_idx is not None:
            ratings[existing_idx]["score"] = score
            ratings[existing_idx]["updated_at"] = now.isoformat()
            created_at = datetime.fromisoformat(ratings[existing_idx]["created_at"])
        else:
            ratings.append({
                "food_name": food_name,
                "score": score,
                "dining_hall": dining_hall,
                "created_at": now.isoformat(),
                "updated_at": now.isoformat(),
            })
            created_at = now

        self._save_ratings_raw(ratings)

        return FoodRating(
            food_name=food_name,
            score=score,
            dining_hall=dining_hall,
            created_at=created_at,
            updated_at=now,
        )

    def get_rating(self, food_name: str) -> FoodRating | None:
        """Get a specific food rating by name."""
        ratings = self._load_ratings_raw()
        for r in ratings:
            if r["food_name"] == food_name:
                return FoodRating(
                    food_name=r["food_name"],
                    score=r["score"],
                    dining_hall=r.get("dining_hall"),
                    created_at=datetime.fromisoformat(r["created_at"]) if r.get("created_at") else datetime.now(),
                    updated_at=datetime.fromisoformat(r["updated_at"]) if r.get("updated_at") else datetime.now(),
                )
        return None

    def delete_rating(self, food_name: str) -> bool:
        """Delete a food rating."""
        ratings = self._load_ratings_raw()
        original_len = len(ratings)
        ratings = [r for r in ratings if r["food_name"] != food_name]

        if len(ratings) < original_len:
            self._save_ratings_raw(ratings)
            return True
        return False

    def get_ratings_dict(self) -> dict[str, int]:
        """Get all ratings as a dictionary of food_name -> score."""
        ratings = self._load_ratings_raw()
        return {r["food_name"]: r["score"] for r in ratings}


# Global storage instance
_storage: Storage | None = None


def get_storage() -> Storage:
    """Get the global storage instance."""
    global _storage
    if _storage is None:
        _storage = Storage()
    return _storage
