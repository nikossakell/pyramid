<script setup lang="ts">
// C10 PortionSelector (ΚΡΑΤΑ): Μικρή / Μεσαία / Μεγάλη, χωρίς γραμμάρια (D3). Χωρίς επιλογή = διακεκομμένο περίγραμμα,
// «απαιτείται πριν την αποθήκευση». Η εικονογράφηση (χέρι / πιάτο) [*εγκρίνει ο διαιτολόγος] — δεν υπάρχει ακόμα.
import { PORTIONS, type Portion } from '@/api/meals'
defineProps<{ modelValue: Portion | null; label?: string }>()
const emit = defineEmits<{ 'update:modelValue': [v: Portion] }>()
</script>

<template>
  <div class="sel" role="radiogroup" :aria-label="label ?? 'Μερίδα'">
    <button v-for="p in PORTIONS" :key="p.value" type="button" role="radio" class="opt" :class="{ 'opt--on': modelValue === p.value, 'opt--none': modelValue === null }"
            :aria-checked="modelValue === p.value" @click="emit('update:modelValue', p.value)">{{ p.label }}</button>
  </div>
</template>

<style scoped>
.sel { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
.opt { height: 44px; border-radius: 12px; border: 1.5px solid var(--color-line); background: var(--color-bg); font-size: calc(14px * var(--text-scale)); font-weight: 500; }
.opt--none { border: 2px dashed var(--color-absent); }
.opt--on { background: var(--color-ink); color: var(--color-on-ink); border: 2px solid var(--color-ink); font-weight: 700; }
</style>
