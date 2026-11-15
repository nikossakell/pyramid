<script setup lang="ts">
// M06 LowConfidence (μετά το S07): «Δεν είμαι σίγουρο. Μήπως είναι…» έως 3 επιλογές (ο server τις στηρίζει) + «Τίποτα από αυτά» → S10.
import BottomSheet from '@/components/ui/BottomSheet.vue'
import type { Alternative } from '@/api/meals'
defineProps<{ open: boolean; options: Alternative[] }>()
const emit = defineEmits<{ pick: [a: Alternative]; none: [] }>()
</script>

<template>
  <BottomSheet :open="open" :dismissible="false" labelled-by="m06-title">
    <h2 id="m06-title" class="t-title">Δεν είμαι σίγουρο. Μήπως είναι…</h2>
    <div class="opts" role="radiogroup" aria-label="Πιθανά φαγητά">
      <button v-for="o in options" :key="o.food_id" type="button" role="radio" aria-checked="false" class="opt pressable" @click="emit('pick', o)">{{ o.name_el }}</button>
    </div>
    <button type="button" class="none pressable" @click="emit('none')">Τίποτα από αυτά</button>
  </BottomSheet>
</template>

<style scoped>
.opts { display: flex; flex-direction: column; gap: 8px; }
.opt { min-height: 56px; border: 1.5px solid var(--color-ink); border-radius: 16px; background: var(--color-bg); color: inherit; font-weight: 600; font-size: calc(17px * var(--text-scale)); padding: 0 16px; text-align: left; }
.none { height: 52px; border: 0; border-radius: 16px; background: var(--color-surface); color: inherit; font-weight: 600; font-size: calc(16px * var(--text-scale)); }
</style>
