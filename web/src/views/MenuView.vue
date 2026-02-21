<script setup lang="ts">
import { ref, onMounted, watch, computed } from 'vue'
import FoodRating from '../components/FoodRating.vue'

interface DiningHall {
  id: number
  name: string
  slug: string
  active: boolean
}

interface MenuItem {
  id: number
  name: string
  food_category: string | null
  icons: string[]
  rating: number  // 0 = unrated, 1-10 = rated (half-star increments)
}

interface MealResponse {
  name: string
  items: MenuItem[]
}

interface DailyMenuResponse {
  dining_hall: DiningHall
  date: string
  meals: Record<string, MealResponse>
}

interface Ranking {
  dining_hall: DiningHall
  total_score: number  // Count of items rated 2-10
  favorite_items: string[]  // 8-10 score (4-5 stars)
  good_items: string[]  // 4-7 score (2-3.5 stars)
  low_items: string[]  // 2-3 score (1-1.5 stars)
}

interface Recommendation {
  date: string
  meal_type: string
  rankings: Ranking[]
  top_pick: Ranking | null
}

const diningHalls = ref<DiningHall[]>([])
const selectedHall = ref<string>('')
const selectedDate = ref(new Date().toISOString().split('T')[0])
const selectedMeal = ref('lunch')
const menu = ref<DailyMenuResponse | null>(null)
const recommendation = ref<Recommendation | null>(null)
const loading = ref(false)
const showRecommendation = ref(true)
const refreshing = ref(false)

// Local ratings cache - key is food_name, value is score
const localRatings = ref<Record<string, number>>({})

// Track pending rating saves
const pendingRatings = ref<Set<string>>(new Set())

const mealTypes = ['breakfast', 'lunch', 'dinner']

onMounted(async () => {
  await Promise.all([
    fetchDiningHalls(),
    fetchRecommendation(),
    fetchExistingRatings()
  ])
})

watch([selectedDate, selectedMeal], async () => {
  if (showRecommendation.value) {
    await fetchRecommendation()
  }
  if (selectedHall.value) {
    await fetchMenu()
  }
})

watch(selectedHall, async () => {
  if (selectedHall.value) {
    showRecommendation.value = false
    await fetchMenu()
  }
})

async function fetchDiningHalls() {
  try {
    const res = await fetch('/api/dining-halls')
    diningHalls.value = await res.json()
  } catch (e) {
    console.error('Failed to fetch dining halls:', e)
  }
}

async function fetchExistingRatings() {
  try {
    const res = await fetch('/api/ratings', { cache: 'no-store' })
    const ratings = await res.json()
    for (const rating of ratings) {
      localRatings.value[rating.food_name] = rating.score
    }
  } catch (e) {
    console.error('Failed to fetch ratings:', e)
  }
}

async function fetchRecommendation() {
  loading.value = true
  try {
    const res = await fetch(
      `/api/recommend/${selectedDate.value}?meal_type=${selectedMeal.value}`,
      { cache: 'no-store' }
    )
    recommendation.value = await res.json()
  } catch (e) {
    console.error('Failed to fetch recommendation:', e)
  } finally {
    loading.value = false
  }
}

async function fetchMenu() {
  if (!selectedHall.value) return
  loading.value = true
  try {
    const res = await fetch(
      `/api/menu/${selectedHall.value}/${selectedDate.value}?meal_type=${selectedMeal.value}`,
      { cache: 'no-store' }
    )
    menu.value = await res.json()
  } catch (e) {
    console.error('Failed to fetch menu:', e)
  } finally {
    loading.value = false
  }
}

async function rateFood(foodName: string, score: number) {
  // Optimistic update - store locally first
  localRatings.value[foodName] = score

  // Track pending save
  pendingRatings.value.add(foodName)

  // Save to server
  try {
    await fetch('/api/ratings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        food_name: foodName,
        score,
        dining_hall: selectedHall.value,
      }),
    })
  } catch (e) {
    console.error('Failed to save rating:', e)
  } finally {
    pendingRatings.value.delete(foodName)
  }
}

async function showRecommendations() {
  // Wait for any pending rating saves to complete
  while (pendingRatings.value.size > 0) {
    await new Promise(resolve => setTimeout(resolve, 50))
  }

  selectedHall.value = ''
  showRecommendation.value = true
  menu.value = null
  await fetchRecommendation()
}

function selectHallFromRanking(slug: string) {
  selectedHall.value = slug
}

// Get rating for a food item (from local cache)
function getRating(foodName: string): number {
  return localRatings.value[foodName] || 0
}

const currentMealItems = computed(() => {
  if (!menu.value?.meals) return []
  const meal = menu.value.meals[selectedMeal.value]
  return meal?.items || []
})

const medals = ['🥇', '🥈', '🥉', '4️⃣', '5️⃣', '6️⃣']

// Quick rate all unrated items
const quickHoverScore = ref(0)

function rateAllWithScore(score: number) {
  for (const item of currentMealItems.value) {
    if (!localRatings.value[item.name]) {
      rateFood(item.name, score)
    }
  }
}

async function refreshCache() {
  refreshing.value = true
  try {
    // Clear cache and re-fetch
    await fetch(`/api/cache/refresh?menu_date=${selectedDate.value}`, {
      method: 'POST',
    })

    // Re-fetch current data
    if (showRecommendation.value) {
      await fetchRecommendation()
    }
    if (selectedHall.value) {
      await fetchMenu()
    }
  } catch (e) {
    console.error('Failed to refresh cache:', e)
  } finally {
    refreshing.value = false
  }
}
</script>

<template>
  <div class="menu-view">
    <div class="controls">
      <div class="control-group">
        <label>Date</label>
        <input type="date" v-model="selectedDate" />
      </div>
      <div class="control-group">
        <label>Meal</label>
        <select v-model="selectedMeal">
          <option v-for="meal in mealTypes" :key="meal" :value="meal">
            {{ meal.charAt(0).toUpperCase() + meal.slice(1) }}
          </option>
        </select>
      </div>
      <div class="control-group">
        <label>Dining Hall</label>
        <select v-model="selectedHall">
          <option value="">-- Select --</option>
          <option v-for="hall in diningHalls" :key="hall.slug" :value="hall.slug">
            {{ hall.name }}
          </option>
        </select>
      </div>
      <button v-if="selectedHall" class="btn-secondary" @click="showRecommendations">
        ← Rankings
      </button>
      <button
        class="btn-refresh"
        :class="{ refreshing }"
        :disabled="refreshing"
        @click="refreshCache"
        title="Refresh menu data"
      >
        <span class="refresh-icon">↻</span>
        <span class="refresh-text">{{ refreshing ? 'Refreshing...' : 'Refresh' }}</span>
      </button>
    </div>

    <div v-if="loading" class="loading">
      <div class="spinner"></div>
      <span>Loading...</span>
    </div>

    <!-- Recommendation View -->
    <div v-else-if="showRecommendation && recommendation" class="recommendation">
      <h2>🏆 Today's Rankings</h2>
      <p class="subtitle">{{ recommendation.date }} · {{ selectedMeal.charAt(0).toUpperCase() + selectedMeal.slice(1) }}</p>

      <div class="rankings">
        <div
          v-for="(rank, index) in recommendation.rankings"
          :key="rank.dining_hall.slug"
          class="ranking-card"
          :class="{ 'top-pick': index === 0 }"
          @click="selectHallFromRanking(rank.dining_hall.slug)"
        >
          <div class="rank-header">
            <span class="medal">{{ medals[index] || `${index + 1}.` }}</span>
            <span class="hall-name">{{ rank.dining_hall.name }}</span>
            <span class="score" :class="{ positive: rank.total_score > 0 }">
              {{ rank.total_score }} rated
            </span>
          </div>
          <div v-if="rank.favorite_items?.length" class="highlights favorites">
            <span class="highlights-label">⭐ 4-5★:</span>
            <span class="highlights-items">{{ rank.favorite_items.slice(0, 4).join(' · ') }}</span>
          </div>
          <div v-if="rank.good_items?.length" class="highlights good">
            <span class="highlights-label">👍 2-3.5★:</span>
            <span class="highlights-items">{{ rank.good_items.slice(0, 4).join(' · ') }}</span>
          </div>
          <div v-if="rank.low_items?.length" class="highlights low">
            <span class="highlights-label">👎 1-1.5★:</span>
            <span class="highlights-items">{{ rank.low_items.slice(0, 4).join(' · ') }}</span>
          </div>
          <div class="view-menu-hint">Click to view menu →</div>
        </div>
      </div>
    </div>

    <!-- Menu View -->
    <div v-else-if="menu" class="menu-content">
      <div class="menu-header">
        <h2>{{ menu.dining_hall.name }}</h2>
        <p class="subtitle">{{ menu.date }} · {{ selectedMeal.charAt(0).toUpperCase() + selectedMeal.slice(1) }}</p>
      </div>

      <div class="menu-toolbar">
        <span class="hint">👆 Click stars to rate (half-star supported)</span>
        <div class="quick-actions" @mouseleave="quickHoverScore = 0">
          <span class="action-label">Quick all:</span>
          <button
            v-for="star in 5"
            :key="star"
            class="quick-star"
            :class="{ filled: star * 2 <= quickHoverScore }"
            @mouseenter="quickHoverScore = star * 2"
            @click="rateAllWithScore(star * 2)"
          >
            ★
          </button>
        </div>
      </div>

      <div v-if="currentMealItems.length === 0" class="no-items">
        No items available for this meal.
      </div>

      <div v-else class="food-list">
        <FoodRating
          v-for="item in currentMealItems"
          :key="item.id"
          :food-name="item.name"
          :current-score="getRating(item.name)"
          :icons="item.icons"
          @rate="(score) => rateFood(item.name, score)"
        />
      </div>
    </div>

    <div v-else class="empty-state">
      <p>Select a dining hall to view the menu</p>
      <p class="hint">Or check out today's rankings above!</p>
    </div>
  </div>
</template>

<style scoped>
.menu-view {
  max-width: 800px;
  margin: 0 auto;
}

.controls {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
  align-items: flex-end;
  background: white;
  padding: 1rem;
  border-radius: 12px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.control-group label {
  font-size: 0.8rem;
  color: #666;
  font-weight: 500;
}

.control-group input,
.control-group select {
  padding: 0.5rem 0.875rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 0.95rem;
  background: #f9fafb;
  transition: all 0.2s;
}

.control-group input:focus,
.control-group select:focus {
  outline: none;
  border-color: #667eea;
  background: white;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.btn-secondary {
  padding: 0.5rem 1rem;
  background: #f3f4f6;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.95rem;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: #e5e7eb;
}

.btn-refresh {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 0.875rem;
  background: #f0fdf4;
  border: 1px solid #86efac;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  color: #16a34a;
  transition: all 0.2s;
  margin-left: auto;
}

.btn-refresh:hover:not(:disabled) {
  background: #dcfce7;
  border-color: #4ade80;
}

.btn-refresh:disabled {
  opacity: 0.7;
  cursor: not-allowed;
}

.refresh-icon {
  font-size: 1.1rem;
  display: inline-block;
  transition: transform 0.3s;
}

.btn-refresh.refreshing .refresh-icon {
  animation: rotate 1s linear infinite;
}

@keyframes rotate {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.loading {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.75rem;
  padding: 3rem;
  color: #666;
}

.spinner {
  width: 20px;
  height: 20px;
  border: 2px solid #e5e7eb;
  border-top-color: #667eea;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.recommendation h2,
.menu-content h2 {
  margin-bottom: 0.25rem;
  font-size: 1.5rem;
}

.subtitle {
  color: #666;
  margin-bottom: 1.5rem;
}

.menu-header {
  margin-bottom: 1rem;
}

.menu-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.5rem 0;
  margin-bottom: 0.5rem;
}

.menu-toolbar .hint {
  font-size: 0.85rem;
  color: #999;
}

.quick-actions {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.action-label {
  font-size: 0.85rem;
  color: #999;
  margin-right: 0.25rem;
}

.quick-star {
  background: none;
  border: none;
  padding: 4px;
  font-size: 1.25rem;
  color: #ddd;
  cursor: pointer;
  transition: all 0.15s;
  line-height: 1;
}

.quick-star:hover {
  transform: scale(1.2);
}

.quick-star.filled {
  color: #fbbf24;
}

.rankings {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.ranking-card {
  background: white;
  padding: 1rem 1.25rem;
  border-radius: 10px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.08);
  cursor: pointer;
  transition: all 0.2s;
  border: 2px solid transparent;
  outline: none;
  -webkit-tap-highlight-color: transparent;
}

.ranking-card:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.12);
  transform: translateY(-2px);
  border-color: #667eea;
}

.ranking-card:active {
  transform: translateY(0);
}

.ranking-card.top-pick {
  border-color: #667eea;
  background: linear-gradient(135deg, #f5f7ff 0%, #fff 100%);
}

.rank-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.medal {
  font-size: 1.5rem;
}

.hall-name {
  font-weight: 600;
  flex: 1;
  font-size: 1.1rem;
}

.score {
  font-weight: 600;
  padding: 0.25rem 0.625rem;
  border-radius: 6px;
  font-size: 0.9rem;
  background: #f3f4f6;
}

.score.positive {
  color: #059669;
  background: #d1fae5;
}

.score.negative {
  color: #dc2626;
  background: #fee2e2;
}

.favorites {
  margin-top: 0.5rem;
  color: #059669;
  font-size: 0.9rem;
  padding-left: 2.25rem;
}

.highlights {
  margin-top: 0.375rem;
  padding-left: 2.25rem;
  font-size: 0.85rem;
}

.highlights.favorites .highlights-label {
  color: #f59e0b;
}

.highlights.good .highlights-label {
  color: #22c55e;
}

.highlights.low .highlights-label {
  color: #ef4444;
}

.highlights-label {
  font-weight: 500;
}

.highlights-items {
  color: #666;
  margin-left: 0.25rem;
}

.view-menu-hint {
  margin-top: 0.75rem;
  padding-left: 2.25rem;
  font-size: 0.85rem;
  color: #9ca3af;
}

.food-list {
  display: flex;
  flex-direction: column;
}

.no-items,
.empty-state {
  text-align: center;
  padding: 3rem;
  color: #666;
  background: white;
  border-radius: 12px;
}

.empty-state .hint {
  margin-top: 0.5rem;
  font-size: 0.9rem;
  color: #9ca3af;
}
</style>
