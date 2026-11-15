<script setup lang="ts">
// C26 EmptyState (ΚΡΑΤΑ): surface, radius 20, εικονίδιο, κείμενο, προαιρετικό κουμπί.
import Icon from './Icon.vue'
defineProps<{ icon?: string; text: string }>()
</script>

<template>
  <div class="empty">
    <span class="ico"><Icon :name="icon ?? 'text'" :size="28" /></span>
    <p class="t-body">{{ text }}</p>
    <slot />
  </div>
</template>

<style scoped>
.empty { background: var(--color-surface); border-radius: 20px; padding: 28px 20px; display: flex; flex-direction: column; align-items: center; gap: 14px; text-align: center; }
.ico { width: 56px; height: 56px; border-radius: 18px; background: var(--color-bg); display: flex; align-items: center; justify-content: center; }
</style>
