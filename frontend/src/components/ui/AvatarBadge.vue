<script setup lang="ts">
// Avatar του παιδιού (C06): κύκλος #B1318E με εικονίδιο. Έτοιμο σετ, χωρίς φωτογραφία ή σώμα (R2).
import { AVATARS } from './avatars'
withDefaults(defineProps<{ avatarId: string | null; size?: number }>(), { size: 40 })
</script>

<template>
  <span class="badge" :style="{ width: size + 'px', height: size + 'px', background: AVATARS.find(a => a.id === avatarId)?.bg ?? 'var(--color-secondary)',
                                 color: AVATARS.find(a => a.id === avatarId)?.fg ?? '#fff' }">
    <svg :width="size * 0.55" :height="size * 0.55" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
      <path :d="AVATARS.find(a => a.id === avatarId)?.path ?? 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21a8 8 0 0 1 16 0'" />
    </svg>
  </span>
</template>

<style scoped>
.badge { border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
</style>
