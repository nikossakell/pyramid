<script setup lang="ts">
// M02 PortionPicker (από S08): «Πόσο μεγάλη ήταν η μερίδα;» με τρεις επιλογές και [*σύγκριση με χέρι ή πιάτο].
import { ref, watch } from 'vue'
import BottomSheet from '@/components/ui/BottomSheet.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { PORTIONS, type Portion } from '@/api/meals'

const props = defineProps<{ open: boolean; name: string; modelValue: Portion | null }>()
const emit = defineEmits<{ close: []; 'update:modelValue': [v: Portion] }>()
const pick = ref<Portion | null>(props.modelValue)
watch(() => props.open, (o) => { if (o) pick.value = props.modelValue })
function ok(): void { if (pick.value) emit('update:modelValue', pick.value); emit('close') }
</script>

<template>
  <BottomSheet :open="open" labelled-by="m02-title" @close="emit('close')">
    <div>
      <div class="t-label muted bold">{{ name }}</div>
      <h2 id="m02-title" class="t-title">Πόσο μεγάλη ήταν η μερίδα;</h2>
    </div>
    <div class="opts" role="radiogroup" aria-label="Μερίδα">
      <button v-for="p in PORTIONS" :key="p.value" type="button" role="radio" class="opt" :class="{ 'opt--on': pick === p.value }" :aria-checked="pick === p.value" @click="pick = p.value">
        <span class="t1">{{ p.label }}</span>
        <span class="t2">[*σύγκριση με χέρι ή πιάτο]</span>
      </button>
    </div>
    <AppButton :disabled="!pick" @click="ok">Εντάξει</AppButton>
  </BottomSheet>
</template>

<style scoped>
.bold { font-weight: 700; }
.opts { display: flex; flex-direction: column; gap: 10px; }
.opt { display: flex; flex-direction: column; align-items: flex-start; gap: 2px; border: 1.5px solid var(--color-line); border-radius: 18px; padding: 10px 14px; background: var(--color-bg); text-align: left; color: inherit; min-height: 60px; }
.opt--on { background: var(--color-ink); color: var(--color-on-ink); border: 2px solid var(--color-ink); }
.t1 { font-weight: 600; font-size: calc(17px * var(--text-scale)); }
.opt--on .t1 { font-weight: 700; }
.t2 { font-size: calc(13px * var(--text-scale)); opacity: 0.8; }
</style>
