<script setup lang="ts">
// C04 Button (ΚΡΑΤΑ): ύψος 52, radius 16, κείμενο 16/600. primary (#F14711, μαύρο κείμενο), secondary, ghost, destructive.
// loading: spinner + κείμενο «…», disabled.
import Icon from './Icon.vue'
withDefaults(defineProps<{ variant?: 'primary' | 'secondary' | 'ghost' | 'destructive'; loading?: boolean; disabled?: boolean;
  type?: 'button' | 'submit'; icon?: string; block?: boolean }>(), { variant: 'primary', loading: false, disabled: false, type: 'button', block: true })
</script>

<template>
  <button :type="type" class="btn pressable" :class="[`btn--${variant}`, { 'btn--block': block }]" :disabled="disabled || loading" :aria-busy="loading || undefined">
    <span v-if="loading" class="spin" aria-hidden="true" />
    <Icon v-else-if="icon" :name="icon" :size="20" />
    <slot />
  </button>
</template>

<style scoped>
.btn { height: 52px; min-height: 52px; border-radius: 16px; border: 0; padding: 0 20px; font-weight: 600; font-size: calc(16px * var(--text-scale)); display: inline-flex; align-items: center; justify-content: center; gap: 10px; }
.btn--block { width: 100%; }
.btn--primary { background: var(--color-primary); color: #000; }
.btn--secondary { background: var(--color-bg); color: var(--color-text); border: 2px solid var(--color-ink); }
.btn--secondary:active { background: var(--color-surface); }
.btn--ghost { background: transparent; color: var(--color-text); }
.btn--ghost:active { background: var(--color-surface); }
.btn--destructive { background: var(--color-ink); color: var(--color-on-ink); }
.btn--destructive:active { background: var(--color-ink-pressed); }
.btn:disabled { background: var(--color-line); color: var(--color-text-muted); border-color: var(--color-line); cursor: default; }
.btn--ghost:disabled { background: transparent; }
.btn--secondary:disabled { background: var(--color-bg); }
.spin { width: 18px; height: 18px; border-radius: 999px; border: 2.5px solid currentColor; border-right-color: transparent; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
:root[data-motion='reduce'] .spin { animation-duration: 2s; }
</style>
