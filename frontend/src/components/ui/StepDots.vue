<script setup lang="ts">
// Δείκτης βημάτων (S03): η τρέχουσα τελεία γίνεται παύλα 28 px, οι προηγούμενες μαύρες, οι επόμενες γκρι.
defineProps<{ total: number; current: number }>()
</script>

<template>
  <div class="steps">
    <div class="dots" aria-hidden="true">
      <span v-for="i in total" :key="i" class="dot" :class="{ 'dot--done': i < current, 'dot--current': i === current }" />
    </div>
    <span class="t-label muted">Βήμα {{ current }} από {{ total }}</span>
  </div>
</template>

<style scoped>
.steps { display: flex; flex-direction: column; gap: 12px; }
.dots { display: flex; gap: 6px; }
.dot { width: 8px; height: 8px; border-radius: 999px; background: var(--color-line); transition: width var(--motion); }
.dot--done { background: var(--color-ink); }
.dot--current { width: 28px; background: var(--color-ink); }
</style>
