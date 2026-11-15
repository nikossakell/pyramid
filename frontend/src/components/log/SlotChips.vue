<script setup lang="ts">
// Επιλογή θέσης γεύματος ως radiogroup από chips (S05, αλλαγή θέσης στο S08/S09).
import { MEAL_SLOTS, type MealSlot } from '@/api/meals'
defineProps<{ modelValue: MealSlot }>()
const emit = defineEmits<{ 'update:modelValue': [v: MealSlot] }>()
</script>

<template>
  <div class="chips" role="radiogroup" aria-label="Γεύμα">
    <button v-for="s in MEAL_SLOTS" :key="s.slot" type="button" role="radio" class="chip" :aria-checked="s.slot === modelValue"
            @click="emit('update:modelValue', s.slot)">{{ s.label }}</button>
  </div>
</template>

<style scoped>
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
</style>
