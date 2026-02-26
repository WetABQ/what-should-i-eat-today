<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import StarRating from '../components/StarRating.vue'
import {
  ratings,
  setRating,
  deleteRating as deleteRatingFromStore,
  fetchRatings,
  type Rating
} from '../stores/ratings'

const loading = ref(false)

onMounted(async () => {
  loading.value = true
  await fetchRatings()
  loading.value = false
})

async function updateRating(foodName: string, score: number) {
  await setRating(foodName, score)
}

async function deleteRatingAction(foodName: string) {
  await deleteRatingFromStore(foodName)
}

// Sort by score descending (computed, so it auto-updates)
const sortedRatings = computed(() => {
  return [...ratings.value].sort((a: Rating, b: Rating) => b.score - a.score)
})

function getScoreClass(score: number): string {
  if (score >= 8) return 'high'  // 4-5 stars
  if (score >= 4) return 'medium'  // 2-3.5 stars
  if (score >= 2) return 'low'  // 1-1.5 stars
  return 'neutral'  // 0.5 stars (score 1)
}

// Stats
const stats = computed(() => {
  const total = ratings.value.length
  const high = ratings.value.filter((r: Rating) => r.score >= 8).length
  const low = ratings.value.filter((r: Rating) => r.score >= 2 && r.score <= 3).length
  return { total, high, low }
})

// Export ratings from server as JSON file
async function exportData() {
  try {
    const res = await fetch('/api/export')
    const data = await res.json()
    data.exported_at = new Date().toISOString()
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `ratings-backup-${new Date().toISOString().split('T')[0]}.json`
    a.click()
    URL.revokeObjectURL(url)
  } catch (e) {
    console.error('Failed to export:', e)
    alert('Export failed')
  }
}

// Import ratings from JSON file to server
function importData() {
  const input = document.createElement('input')
  input.type = 'file'
  input.accept = '.json'
  input.onchange = async (e) => {
    const file = (e.target as HTMLInputElement).files?.[0]
    if (!file) return

    try {
      const text = await file.text()
      const data = JSON.parse(text)

      const ratingsData = Array.isArray(data) ? data : (data.ratings || [])
      await fetch('/api/import', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ratings: ratingsData }),
      })

      await fetchRatings()
      alert(`Imported ${ratingsData.length} ratings`)
    } catch (e) {
      console.error('Failed to import:', e)
      alert('Import failed - invalid file format')
    }
  }
  input.click()
}
</script>

<template>
  <div class="settings-view">
    <!-- Ratings Section -->
    <div class="section ratings-section">
      <div class="section-header">
        <h2>My Ratings</h2>
        <div class="header-actions">
          <button class="btn-secondary" @click="importData">Import</button>
          <button class="btn-secondary" @click="exportData">Export</button>
        </div>
      </div>
      <p class="subtitle">Click stars to modify ratings. List auto-sorts by score.</p>

      <div class="stats">
      <div class="stat">
        <span class="stat-value">{{ stats.total }}</span>
        <span class="stat-label">Total</span>
      </div>
      <div class="stat high">
        <span class="stat-value">{{ stats.high }}</span>
        <span class="stat-label">Favorites (4-5★)</span>
      </div>
      <div class="stat low">
        <span class="stat-value">{{ stats.low }}</span>
        <span class="stat-label">Avoid (1-1.5★)</span>
      </div>
    </div>

    <div v-if="loading" class="loading">Loading...</div>

    <div v-else-if="sortedRatings.length === 0" class="empty">
      No ratings yet. Rate foods from the Menu page!
    </div>

    <div v-else class="ratings-list">
      <TransitionGroup name="list">
        <div
          v-for="rating in sortedRatings"
          :key="rating.food_name"
          class="rating-item"
          :class="getScoreClass(rating.score)"
        >
          <div class="rating-info">
            <StarRating
              :model-value="rating.score"
              @update:model-value="(score) => updateRating(rating.food_name, score)"
              size="sm"
            />
            <span class="food-name">{{ rating.food_name }}</span>
          </div>
          <button class="btn-delete" @click="deleteRatingAction(rating.food_name)">
            ×
          </button>
        </div>
      </TransitionGroup>
    </div>
    </div>
  </div>
</template>

<style scoped>
.settings-view {
  max-width: 800px;
  margin: 0 auto;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.25rem;
}

.section-header h2 {
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-secondary {
  padding: 0.5rem 1rem;
  background: #f3f4f6;
  color: #374151;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.btn-secondary:hover {
  background: #e5e7eb;
}

h2 {
  margin-bottom: 0.25rem;
}

.subtitle {
  color: #666;
  margin-bottom: 1.5rem;
}

.stats {
  display: flex;
  gap: 1rem;
  margin-bottom: 1.5rem;
}

.stat {
  background: white;
  padding: 1rem 1.5rem;
  border-radius: 8px;
  text-align: center;
  flex: 1;
}

.stat-value {
  display: block;
  font-size: 1.75rem;
  font-weight: 600;
  color: #333;
}

.stat-label {
  font-size: 0.85rem;
  color: #666;
}

.stat.high .stat-value {
  color: #22c55e;
}

.stat.low .stat-value {
  color: #ef4444;
}

.loading,
.empty {
  text-align: center;
  padding: 3rem;
  color: #666;
  background: white;
  border-radius: 8px;
}

.ratings-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.rating-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.625rem 1rem;
  background: white;
  border-radius: 6px;
  border-left: 3px solid #e5e7eb;
}

.rating-item.high {
  border-left-color: #22c55e;
  background: linear-gradient(90deg, #f0fdf4 0%, white 15%);
}

.rating-item.medium {
  border-left-color: #fbbf24;
}

.rating-item.low {
  border-left-color: #ef4444;
  background: linear-gradient(90deg, #fef2f2 0%, white 15%);
}

.rating-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.food-name {
  font-weight: 500;
}

.btn-delete {
  width: 28px;
  height: 28px;
  padding: 0;
  background: none;
  border: 1px solid #e5e7eb;
  border-radius: 4px;
  cursor: pointer;
  font-size: 1.25rem;
  color: #999;
  line-height: 1;
  transition: all 0.2s;
}

.btn-delete:hover {
  background: #fee2e2;
  border-color: #fca5a5;
  color: #dc2626;
}

/* List transition */
.list-move,
.list-enter-active,
.list-leave-active {
  transition: all 0.3s ease;
}

.list-enter-from,
.list-leave-to {
  opacity: 0;
  transform: translateX(-30px);
}

.list-leave-active {
  position: absolute;
}
</style>
