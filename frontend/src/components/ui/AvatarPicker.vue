<script setup lang="ts">
// C06 AvatarPicker (ΚΡΑΤΑ): πλέγμα 4 × 72, επιλεγμένο = μαύρο δαχτυλίδι + σημάδι.
import Icon from './Icon.vue'
import { AVATARS } from './avatars'
defineProps<{ modelValue: string | null }>()
const emit = defineEmits<{ 'update:modelValue': [id: string] }>()
</script>

<template>
  <fieldset class="picker">
    <legend class="visually-hidden">Avatar</legend>
    <button v-for="a in AVATARS" :key="a.id" type="button" class="avatar" :class="{ 'avatar--selected': a.id === modelValue }"
            :aria-label="a.id === modelValue ? `${a.label}, επιλεγμένο` : a.label" :aria-pressed="a.id === modelValue"
            @click="emit('update:modelValue', a.id)">
      <span class="face" :style="{ background: a.bg, color: a.fg }">
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path :d="a.path" /></svg>
      </span>
      <span v-if="a.id === modelValue" class="tick"><Icon name="check" :size="14" :stroke="3" /></span>
    </button>
  </fieldset>
</template>

<style scoped>
.picker { border: 0; padding: 0; margin: 0; display: grid; grid-template-columns: repeat(4, 72px); gap: 18px 22px; justify-content: center; }
.avatar { position: relative; width: 72px; height: 72px; border-radius: 999px; border: 0; padding: 0; background: transparent; }
.avatar--selected { border: 3px solid var(--color-ink); padding: 3px; background: var(--color-bg); }
.face { width: 100%; height: 100%; border-radius: 999px; display: flex; align-items: center; justify-content: center; }
.tick { position: absolute; right: -2px; bottom: -2px; width: 26px; height: 26px; border-radius: 999px; background: var(--color-ink); color: var(--color-on-ink); display: flex; align-items: center; justify-content: center; border: 2px solid var(--color-bg); }
</style>
