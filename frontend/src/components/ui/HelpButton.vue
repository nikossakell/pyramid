<script setup lang="ts">
// C01 HelpButton (ΚΡΑΤΑ): pill #FEB211, μαύρο περίγραμμα 2px, 44 ύψος. Ανοίγει το M01 HelpSheet. Ίδιο στο σκοτεινό θέμα.
import Icon from './Icon.vue'
import { useUiStore } from '@/stores/ui'
const ui = useUiStore()
</script>

<template>
  <button type="button" class="help pressable" aria-label="Βοήθεια: γραμμές υποστήριξης" @click="ui.helpOpen = true">
    <Icon name="help" :size="20" :stroke="2.2" />
    <span>Βοήθεια</span>
  </button>
</template>

<style scoped>
.help {
  height: 44px; min-width: 44px; padding: 0 16px 0 12px; border-radius: 999px;
  background: var(--color-help); color: #000; border: 2px solid #000;
  font-weight: 700; font-size: calc(15px * var(--text-scale)); display: inline-flex; align-items: center; gap: 6px; flex: none;
}
.help:active { background: var(--color-help-pressed); }
</style>
