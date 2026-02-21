<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import StarRating from '../components/StarRating.vue'
import {
  ratings,
  setRating,
  deleteRating as deleteRatingFromStore,
  importRatings,
  exportRatings,
  type Rating
} from '../stores/ratings'

interface Preset {
  name: string
  rating_count: number
  created_at: string
  description: string
}

const loading = ref(false)

// Presets state (still server-based for now)
const presets = ref<Preset[]>([])
const activePreset = ref<string | null>(null)
const showNewPresetModal = ref(false)
const newPresetName = ref('')
const newPresetDescription = ref('')
const presetLoading = ref(false)

onMounted(async () => {
  // Ratings already loaded from localStorage
  // Only fetch presets from server
  await fetchPresets()
})

function updateRating(foodName: string, score: number) {
  setRating(foodName, score)
}

function deleteRating(foodName: string) {
  deleteRatingFromStore(foodName)
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

// Presets
async function fetchPresets() {
  try {
    const res = await fetch('/api/presets')
    const data = await res.json()
    presets.value = data.presets
    activePreset.value = data.active
  } catch (e) {
    console.error('Failed to fetch presets:', e)
  }
}

async function loadPreset(name: string) {
  if (!confirm(`Load preset "${name}"? This will replace all current ratings.`)) {
    return
  }

  presetLoading.value = true
  try {
    await fetch(`/api/presets/${encodeURIComponent(name)}/load`, {
      method: 'POST',
    })
    activePreset.value = name
    await fetchRatings()
  } catch (e) {
    console.error('Failed to load preset:', e)
  } finally {
    presetLoading.value = false
  }
}

async function createPreset() {
  if (!newPresetName.value.trim()) return

  presetLoading.value = true
  try {
    await fetch('/api/presets', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: newPresetName.value.trim(),
        description: newPresetDescription.value.trim(),
      }),
    })
    await fetchPresets()
    showNewPresetModal.value = false
    newPresetName.value = ''
    newPresetDescription.value = ''
  } catch (e) {
    console.error('Failed to create preset:', e)
  } finally {
    presetLoading.value = false
  }
}

async function deletePreset(name: string) {
  if (!confirm(`Delete preset "${name}"? This cannot be undone.`)) {
    return
  }

  try {
    await fetch(`/api/presets/${encodeURIComponent(name)}`, {
      method: 'DELETE',
    })
    await fetchPresets()
  } catch (e) {
    console.error('Failed to delete preset:', e)
  }
}

function formatDate(dateStr: string): string {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  return date.toLocaleDateString()
}

// Sync to server (for Telegram bot)
const syncing = ref(false)

async function syncToServer() {
  syncing.value = true
  try {
    // Push all ratings to server
    const allRatings = exportRatings()
    await fetch('/api/ratings/sync', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ratings: allRatings }),
    })
    alert(`Synced ${allRatings.length} ratings to server. Telegram bot will use these ratings.`)
  } catch (e) {
    console.error('Failed to sync:', e)
    alert('Sync failed')
  } finally {
    syncing.value = false
  }
}

// Import/Export (using localStorage)
function exportData() {
  try {
    const data = {
      ratings: exportRatings(),
      exported_at: new Date().toISOString(),
    }
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

      // Support both old format (data.ratings) and new format (direct array)
      const ratingsData = Array.isArray(data) ? data : (data.ratings || [])
      importRatings(ratingsData)

      alert(`Imported ${ratingsData.length} ratings to browser storage`)
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
    <!-- Presets Section -->
    <div class="section presets-section">
      <div class="section-header">
        <h2>Presets</h2>
        <div class="header-actions">
          <button class="btn-secondary" @click="importData">Import</button>
          <button class="btn-secondary" @click="exportData">Export</button>
          <button
            class="btn-sync"
            :disabled="syncing"
            @click="syncToServer"
            title="Sync ratings to server for Telegram bot"
          >
            {{ syncing ? 'Syncing...' : '↑ Sync to Server' }}
          </button>
        </div>
      </div>

      <div v-if="presets.length === 0" class="empty-presets">
        No presets yet. Save your current ratings as a preset to get started.
      </div>

      <div v-else class="presets-list">
        <div
          v-for="preset in presets"
          :key="preset.name"
          class="preset-card"
          :class="{ active: preset.name === activePreset }"
        >
          <div class="preset-info">
            <div class="preset-name">
              {{ preset.name }}
              <span v-if="preset.name === activePreset" class="active-badge">Active</span>
            </div>
            <div class="preset-meta">
              {{ preset.rating_count }} ratings · {{ formatDate(preset.created_at) }}
            </div>
            <div v-if="preset.description" class="preset-description">
              {{ preset.description }}
            </div>
          </div>
          <div class="preset-actions">
            <button
              v-if="preset.name !== activePreset"
              class="btn-load"
              :disabled="presetLoading"
              @click="loadPreset(preset.name)"
            >
              Load
            </button>
            <button
              class="btn-delete-preset"
              @click="deletePreset(preset.name)"
            >
              Delete
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- New Preset Modal -->
    <div v-if="showNewPresetModal" class="modal-overlay" @click.self="showNewPresetModal = false">
      <div class="modal">
        <h3>Save as New Preset</h3>
        <div class="form-group">
          <label>Preset Name</label>
          <input
            v-model="newPresetName"
            type="text"
            placeholder="e.g., my-preferences"
            @keyup.enter="createPreset"
          />
        </div>
        <div class="form-group">
          <label>Description (optional)</label>
          <input
            v-model="newPresetDescription"
            type="text"
            placeholder="e.g., My personal food preferences"
          />
        </div>
        <div class="modal-actions">
          <button class="btn-secondary" @click="showNewPresetModal = false">Cancel</button>
          <button
            class="btn-primary"
            :disabled="!newPresetName.trim() || presetLoading"
            @click="createPreset"
          >
            Save Preset
          </button>
        </div>
      </div>
    </div>

    <!-- Ratings Section -->
    <div class="section ratings-section">
      <h2>My Ratings</h2>
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
          <button class="btn-delete" @click="deleteRating(rating.food_name)">
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

.section {
  margin-bottom: 2rem;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.section-header h2 {
  margin: 0;
}

.header-actions {
  display: flex;
  gap: 0.5rem;
}

h2 {
  margin-bottom: 0.25rem;
}

.subtitle {
  color: #666;
  margin-bottom: 1.5rem;
}

/* Presets */
.presets-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.preset-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.25rem;
  background: white;
  border-radius: 8px;
  border: 2px solid transparent;
  transition: all 0.2s;
}

.preset-card.active {
  border-color: #22c55e;
  background: linear-gradient(90deg, #f0fdf4 0%, white 20%);
}

.preset-info {
  flex: 1;
}

.preset-name {
  font-weight: 600;
  font-size: 1.05rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.active-badge {
  font-size: 0.75rem;
  font-weight: 500;
  color: #16a34a;
  background: #dcfce7;
  padding: 0.125rem 0.5rem;
  border-radius: 4px;
}

.preset-meta {
  font-size: 0.85rem;
  color: #666;
  margin-top: 0.25rem;
}

.preset-description {
  font-size: 0.9rem;
  color: #888;
  margin-top: 0.25rem;
}

.preset-actions {
  display: flex;
  gap: 0.5rem;
}

.btn-primary {
  padding: 0.5rem 1rem;
  background: #667eea;
  color: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.btn-primary:hover:not(:disabled) {
  background: #5a67d8;
}

.btn-primary:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-load {
  padding: 0.375rem 0.875rem;
  background: #f0fdf4;
  color: #16a34a;
  border: 1px solid #86efac;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.btn-load:hover:not(:disabled) {
  background: #dcfce7;
}

.btn-load:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-delete-preset {
  padding: 0.375rem 0.75rem;
  background: none;
  color: #999;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.85rem;
  transition: all 0.2s;
}

.btn-delete-preset:hover {
  background: #fee2e2;
  border-color: #fca5a5;
  color: #dc2626;
}

.empty-presets {
  padding: 2rem;
  text-align: center;
  color: #666;
  background: white;
  border-radius: 8px;
}

/* Modal */
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal {
  background: white;
  padding: 1.5rem;
  border-radius: 12px;
  width: 90%;
  max-width: 400px;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.modal h3 {
  margin: 0 0 1.25rem 0;
}

.form-group {
  margin-bottom: 1rem;
}

.form-group label {
  display: block;
  font-size: 0.85rem;
  color: #666;
  margin-bottom: 0.375rem;
}

.form-group input {
  width: 100%;
  padding: 0.625rem 0.875rem;
  border: 1px solid #e5e7eb;
  border-radius: 6px;
  font-size: 0.95rem;
  transition: all 0.2s;
  box-sizing: border-box;
}

.form-group input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.modal-actions {
  display: flex;
  justify-content: flex-end;
  gap: 0.5rem;
  margin-top: 1.5rem;
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

.btn-sync {
  padding: 0.5rem 1rem;
  background: #dbeafe;
  color: #1d4ed8;
  border: 1px solid #93c5fd;
  border-radius: 6px;
  cursor: pointer;
  font-size: 0.9rem;
  transition: all 0.2s;
}

.btn-sync:hover:not(:disabled) {
  background: #bfdbfe;
}

.btn-sync:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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
