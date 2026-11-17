<script setup lang="ts">
// C27 Toast (ΚΡΑΤΑ): μαύρο, radius 16· επιτυχία με πράσινο κύκλο, σφάλμα με τρίγωνο και «Ξανά». Μόνο τεχνικά σφάλματα.
import Icon from './Icon.vue'
import { useUiStore } from '@/stores/ui'
const ui = useUiStore()
</script>

<template>
  <div class="host" aria-live="polite">
    <TransitionGroup name="toast">
      <div v-for="t in ui.toasts" :key="t.id" class="toast" :role="t.kind === 'error' ? 'alert' : 'status'">
        <span v-if="t.kind === 'success'" class="ok"><Icon name="check" :size="16" :stroke="3" /></span>
        <Icon v-else :name="t.kind === 'error' ? 'warning' : 'info'" :size="22" />
        <span class="text">{{ t.text }}</span>
        <button v-if="t.action" type="button" class="act" @click="t.action.run(); ui.dismiss(t.id)">{{ t.action.label }}</button>
      </div>
    </TransitionGroup>
  </div>
</template>

<style scoped>
.host { position: fixed; left: 16px; right: 16px; bottom: calc(100px + var(--safe-bottom)); z-index: 70; display: flex; flex-direction: column; gap: 8px; pointer-events: none; }
.toast { pointer-events: auto; background: #000; color: #fff; border-radius: 16px; padding: 10px 8px 10px 16px; display: flex; align-items: center; gap: 12px; font-size: calc(15px * var(--text-scale)); box-shadow: var(--shadow-card); }
.ok { width: 28px; height: 28px; border-radius: 999px; background: var(--color-positive); color: #fff; display: flex; align-items: center; justify-content: center; flex: none; }
.text { flex: 1; }
.act { height: 44px; padding: 0 12px; border: 0; border-radius: 12px; background: #2b2926; color: #fff; font-weight: 700; font-size: calc(14px * var(--text-scale)); }
.toast-enter-active, .toast-leave-active { transition: opacity var(--motion), transform var(--motion); }
.toast-enter-from, .toast-leave-to { opacity: 0; transform: translateY(8px); }
@media (min-width: 600px) and (max-width: 1023.98px) { .host { left: 50%; right: auto; transform: translateX(-50%); width: min(100% - 32px, var(--content-max-medium)); } }
/* expanded: κάτω δεξιά (C27) */
@media (min-width: 1024px) { .host { left: auto; right: 24px; bottom: 24px; width: 380px; } }
</style>
