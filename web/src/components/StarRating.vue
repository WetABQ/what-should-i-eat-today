<script setup lang="ts">
import { ref, computed } from 'vue'

interface Props {
  modelValue: number  // 1-10 (0 = unrated)
  readonly?: boolean
  size?: 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  modelValue: 0,
  readonly: false,
  size: 'md',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: number): void
}>()

const hoverScore = ref(0)
const isAnimating = ref(false)

const displayScore = computed(() => hoverScore.value || props.modelValue)

// Convert score (1-10) to star fill percentage for each star
const getStarFill = (starIndex: number): number => {
  const score = displayScore.value
  const starScore = starIndex * 2  // Each star = 2 points

  if (score >= starScore) {
    return 100  // Full star
  } else if (score >= starScore - 1) {
    return 50  // Half star
  }
  return 0  // Empty star
}

const handleMouseMove = (starIndex: number, event: MouseEvent) => {
  if (props.readonly) return

  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const x = event.clientX - rect.left
  const isLeftHalf = x < rect.width / 2

  // Left half = odd score, right half = even score
  hoverScore.value = isLeftHalf ? starIndex * 2 - 1 : starIndex * 2
}

const handleClick = (starIndex: number, event: MouseEvent) => {
  if (props.readonly) return

  const target = event.currentTarget as HTMLElement
  const rect = target.getBoundingClientRect()
  const x = event.clientX - rect.left
  const isLeftHalf = x < rect.width / 2

  const score = isLeftHalf ? starIndex * 2 - 1 : starIndex * 2

  // Animate
  isAnimating.value = true
  setTimeout(() => {
    isAnimating.value = false
  }, 300)

  emit('update:modelValue', score)
}

const clearHover = () => {
  hoverScore.value = 0
}

const sizeClass = computed(() => `size-${props.size}`)
</script>

<template>
  <div
    class="star-rating"
    :class="[sizeClass, { readonly, hovering: hoverScore > 0, animating: isAnimating }]"
    @mouseleave="clearHover"
  >
    <div
      v-for="starIndex in 5"
      :key="starIndex"
      class="star"
      @mousemove="handleMouseMove(starIndex, $event)"
      @click="handleClick(starIndex, $event)"
    >
      <!-- Background (empty) star -->
      <span class="star-empty">★</span>
      <!-- Filled star with clip -->
      <span
        class="star-filled"
        :style="{ clipPath: `inset(0 ${100 - getStarFill(starIndex)}% 0 0)` }"
      >★</span>
    </div>
  </div>
</template>

<style scoped>
.star-rating {
  display: inline-flex;
  gap: 2px;
}

.star-rating.readonly {
  pointer-events: none;
}

.star {
  position: relative;
  cursor: pointer;
  line-height: 1;
}

.star-rating.readonly .star {
  cursor: default;
}

.star-empty,
.star-filled {
  display: block;
  transition: transform 0.15s;
}

.star-empty {
  color: #e5e7eb;
}

.star-filled {
  position: absolute;
  top: 0;
  left: 0;
  color: #fbbf24;
  transition: clip-path 0.1s;
}

/* Hover effect */
.star-rating:not(.readonly) .star:hover .star-empty,
.star-rating:not(.readonly) .star:hover .star-filled {
  transform: scale(1.15);
}

.star-rating.hovering .star-filled {
  color: #fcd34d;
}

/* Animation */
.star-rating.animating .star-filled {
  animation: pop 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
}

@keyframes pop {
  0% { transform: scale(1); }
  50% { transform: scale(1.2); }
  100% { transform: scale(1); }
}

/* Sizes */
.size-sm .star-empty,
.size-sm .star-filled {
  font-size: 1rem;
}

.size-md .star-empty,
.size-md .star-filled {
  font-size: 1.5rem;
}

.size-lg .star-empty,
.size-lg .star-filled {
  font-size: 2rem;
}
</style>
