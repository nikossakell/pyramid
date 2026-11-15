<script setup lang="ts">
// C28 OfflineBanner (ΚΡΑΤΑ): μαύρη λωρίδα offline· «Συνδέθηκες ξανά.» σε surface, κρύβεται αυτόματα.
import Icon from './Icon.vue'
import { useUiStore } from '@/stores/ui'
const ui = useUiStore()
withDefaults(defineProps<{ text?: string }>(), { text: 'Είσαι εκτός σύνδεσης. Βλέπεις ό,τι είναι αποθηκευμένο στο κινητό.' })
</script>

<template>
  <div v-if="!ui.online" class="banner" role="status"><Icon name="offline" :size="20" /><span>{{ text }}</span></div>
  <div v-else-if="ui.reconnected" class="banner banner--ok" role="status">
    <span class="ok"><Icon name="check" :size="14" :stroke="3" /></span><span>Συνδέθηκες ξανά.</span>
  </div>
</template>

<style scoped>
.banner { padding-top: calc(10px + var(--safe-top)); }
.banner--ok { background: var(--color-surface); color: var(--color-text); }
.ok { width: 24px; height: 24px; border-radius: 999px; background: var(--color-positive); color: #fff; display: inline-flex; align-items: center; justify-content: center; }
</style>
