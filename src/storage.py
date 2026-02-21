"""JSON-based storage for ratings and presets."""

import json
from datetime import datetime
from pathlib import Path

from .models import FoodRating

DATA_DIR = Path(__file__).parent.parent / "data"
RATINGS_FILE = DATA_DIR / "ratings.json"
PRESETS_DIR = DATA_DIR / "presets"
ACTIVE_PRESET_FILE = DATA_DIR / "active_preset.txt"


class Storage:
    """Storage class for managing ratings and presets in JSON files."""

    def __init__(self, data_dir: Path | None = None):
        """Initialize storage with optional custom data directory."""
        self.data_dir = data_dir or DATA_DIR
        self.ratings_file = self.data_dir / "ratings.json"
        self._ensure_data_dir()

    def _ensure_data_dir(self) -> None:
        """Ensure the data directory exists."""
        self.data_dir.mkdir(parents=True, exist_ok=True)

    # === Ratings ===

    def _load_ratings_raw(self) -> list[dict]:
        """Load ratings from JSON file (always fresh read)."""
        if not self.ratings_file.exists():
            return []

        try:
            with open(self.ratings_file) as f:
                return json.load(f)
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

        # Find existing rating
        existing_idx = None
        for i, r in enumerate(ratings):
            if r["food_name"] == food_name:
                existing_idx = i
                break

        if existing_idx is not None:
            # Update existing
            ratings[existing_idx]["score"] = score
            ratings[existing_idx]["updated_at"] = now.isoformat()
            created_at = datetime.fromisoformat(ratings[existing_idx]["created_at"])
        else:
            # Add new
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

    # === Presets ===

    def _ensure_presets_dir(self) -> None:
        """Ensure the presets directory exists."""
        PRESETS_DIR.mkdir(parents=True, exist_ok=True)

    def list_presets(self) -> list[dict]:
        """List all available presets with their metadata."""
        self._ensure_presets_dir()
        presets = []

        for preset_file in sorted(PRESETS_DIR.glob("*.json")):
            try:
                with open(preset_file) as f:
                    data = json.load(f)
                presets.append({
                    "name": preset_file.stem,
                    "rating_count": len(data.get("ratings", [])),
                    "created_at": data.get("created_at"),
                    "description": data.get("description", ""),
                })
            except (json.JSONDecodeError, KeyError):
                continue

        return presets

    def save_preset(self, name: str, description: str = "") -> dict:
        """Save current ratings as a preset."""
        self._ensure_presets_dir()

        # Load current ratings
        ratings = self._load_ratings_raw()
        preset_ratings = []
        for r in ratings:
            preset_ratings.append({
                "food_name": r["food_name"],
                "score": r["score"],
                "dining_hall": r.get("dining_hall"),
            })

        preset_data = {
            "name": name,
            "description": description,
            "created_at": datetime.now().isoformat(),
            "ratings": preset_ratings,
        }

        preset_file = PRESETS_DIR / f"{name}.json"
        with open(preset_file, "w") as f:
            json.dump(preset_data, f, indent=2)

        return {
            "name": name,
            "rating_count": len(preset_ratings),
            "created_at": preset_data["created_at"],
            "description": description,
        }

    def load_preset(self, name: str) -> bool:
        """Load a preset, replacing current ratings."""
        preset_file = PRESETS_DIR / f"{name}.json"
        if not preset_file.exists():
            return False

        try:
            with open(preset_file) as f:
                data = json.load(f)
        except json.JSONDecodeError:
            return False

        # Clear current ratings and load preset ratings
        now = datetime.now().isoformat()
        ratings = data.get("ratings", [])

        # Convert to full rating format
        new_ratings = []
        for r in ratings:
            new_ratings.append({
                "food_name": r["food_name"],
                "score": r["score"],
                "dining_hall": r.get("dining_hall"),
                "created_at": now,
                "updated_at": now,
            })

        self._save_ratings_raw(new_ratings)

        # Save active preset name
        self._set_active_preset(name)

        return True

    def delete_preset(self, name: str) -> bool:
        """Delete a preset."""
        preset_file = PRESETS_DIR / f"{name}.json"
        if preset_file.exists():
            preset_file.unlink()
            # Clear active preset if it was the deleted one
            if self.get_active_preset() == name:
                self._set_active_preset(None)
            return True
        return False

    def get_active_preset(self) -> str | None:
        """Get the name of the currently active preset."""
        if not ACTIVE_PRESET_FILE.exists():
            return None
        try:
            return ACTIVE_PRESET_FILE.read_text().strip() or None
        except Exception:
            return None

    def _set_active_preset(self, name: str | None) -> None:
        """Set the active preset name."""
        if name:
            ACTIVE_PRESET_FILE.write_text(name)
        elif ACTIVE_PRESET_FILE.exists():
            ACTIVE_PRESET_FILE.unlink()


# Global storage instance
_storage: Storage | None = None


def get_storage() -> Storage:
    """Get the global storage instance."""
    global _storage
    if _storage is None:
        _storage = Storage()
    return _storage
