/**
 * Ratings store using localStorage for persistence.
 * No server dependency - all data stays in browser.
 */

import { ref, watch } from 'vue'

export interface Rating {
  food_name: string
  score: number  // 1-10
  dining_hall: string | null
  created_at: string
  updated_at: string
}

const STORAGE_KEY = 'food-ratings'

// Load ratings from localStorage
function loadRatings(): Rating[] {
  try {
    const data = localStorage.getItem(STORAGE_KEY)
    return data ? JSON.parse(data) : []
  } catch {
    return []
  }
}

// Save ratings to localStorage
function saveRatings(ratings: Rating[]) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ratings))
}

// Reactive ratings list
export const ratings = ref<Rating[]>(loadRatings())

// Watch for changes and save to localStorage
watch(ratings, (newRatings) => {
  saveRatings(newRatings)
}, { deep: true })

// Get ratings as a dictionary (food_name -> score)
export function getRatingsDict(): Record<string, number> {
  const dict: Record<string, number> = {}
  for (const rating of ratings.value) {
    dict[rating.food_name] = rating.score
  }
  return dict
}

// Get score for a specific food
export function getRating(foodName: string): number {
  const rating = ratings.value.find(r => r.food_name === foodName)
  return rating?.score || 0
}

// Set or update a rating
export function setRating(foodName: string, score: number, diningHall: string | null = null) {
  const now = new Date().toISOString()
  const existing = ratings.value.find(r => r.food_name === foodName)

  if (existing) {
    existing.score = score
    existing.updated_at = now
    if (diningHall) existing.dining_hall = diningHall
  } else {
    ratings.value.push({
      food_name: foodName,
      score,
      dining_hall: diningHall,
      created_at: now,
      updated_at: now,
    })
  }
}

// Delete a rating
export function deleteRating(foodName: string) {
  const index = ratings.value.findIndex(r => r.food_name === foodName)
  if (index !== -1) {
    ratings.value.splice(index, 1)
  }
}

// Import ratings (replace all)
export function importRatings(newRatings: Rating[]) {
  ratings.value = newRatings
}

// Export ratings
export function exportRatings(): Rating[] {
  return ratings.value
}

// Clear all ratings
export function clearRatings() {
  ratings.value = []
}
