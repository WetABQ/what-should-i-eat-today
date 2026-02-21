<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import StarRating from './StarRating.vue'

interface Props {
  foodName: string
  currentScore: number  // 1-10 (0 = unrated)
  icons?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  currentScore: 0,
  icons: () => [],
})

const emit = defineEmits<{
  (e: 'rate', score: number): void
}>()

const localScore = ref(props.currentScore)

// Sync with parent if currentScore changes
watch(() => props.currentScore, (newVal) => {
  localScore.value = newVal
})

const handleRate = (score: number) => {
  localScore.value = score
  emit('rate', score)
}

const hasRating = computed(() => localScore.value > 0)
</script>

<template>
  <div class="food-rating" :class="{ rated: hasRating }">
    <div class="food-info">
      <span class="food-name">{{ foodName }}</span>
      <span v-if="icons.length" class="icons">
        {{ icons.slice(0, 3).join(' · ') }}
      </span>
    </div>
    <StarRating
      :model-value="localScore"
      @update:model-value="handleRate"
      size="md"
    />
  </div>
</template>

<style scoped>
.food-rating {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  background: white;
  border-radius: 8px;
  margin-bottom: 6px;
  transition: box-shadow 0.2s, transform 0.2s;
  border-left: 3px solid transparent;
}

.food-rating:hover {
  box-shadow: 0 2px 12px rgba(0,0,0,0.1);
  transform: translateX(2px);
}

.food-rating.rated {
  border-left-color: #22c55e;
  background: linear-gradient(90deg, #f0fdf4 0%, white 20%);
}

.food-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex: 1;
  min-width: 0;
}

.food-name {
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.icons {
  color: #999;
  font-size: 0.8rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
