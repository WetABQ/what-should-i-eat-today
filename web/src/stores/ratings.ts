/**
 * Ratings store backed by server API.
 * All reads/writes go through the backend — no localStorage.
 */

import { ref } from 'vue'

export interface Rating {
  food_name: string
  score: number  // 1-10
  dining_hall: string | null
  created_at: string
  updated_at: string
}

// Reactive ratings list
export const ratings = ref<Rating[]>([])

// Fetch all ratings from server
export async function fetchRatings() {
  try {
    const res = await fetch('/api/ratings')
    ratings.value = await res.json()
  } catch (e) {
    console.error('Failed to fetch ratings:', e)
  }
}

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

// Set or update a rating via server API
export async function setRating(foodName: string, score: number, diningHall: string | null = null) {
  try {
    const res = await fetch('/api/ratings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ food_name: foodName, score, dining_hall: diningHall }),
    })
    const saved: Rating = await res.json()

    // Update local ref
    const existing = ratings.value.find(r => r.food_name === foodName)
    if (existing) {
      existing.score = saved.score
      existing.updated_at = saved.updated_at
      if (saved.dining_hall) existing.dining_hall = saved.dining_hall
    } else {
      ratings.value.push(saved)
    }
  } catch (e) {
    console.error('Failed to save rating:', e)
  }
}

// Delete a rating via server API
export async function deleteRating(foodName: string) {
  try {
    await fetch(`/api/ratings/${encodeURIComponent(foodName)}`, { method: 'DELETE' })
    const index = ratings.value.findIndex(r => r.food_name === foodName)
    if (index !== -1) {
      ratings.value.splice(index, 1)
    }
  } catch (e) {
    console.error('Failed to delete rating:', e)
  }
}
