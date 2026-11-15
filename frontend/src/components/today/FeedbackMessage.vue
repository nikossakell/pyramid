<script setup lang="ts">
// C14 FeedbackMessage (ΑΛΛΑΞΕ): τα κείμενα του /feedback/today όπως έρχονται (εγκεκριμένα πρότυπα, presenter στον server).
// Το API δεν ξεχωρίζει ενθάρρυνση / πρόταση: το πρώτο μήνυμα σε surface με το σήμα, τα επόμενα με περίγραμμα.
import PyramidMark from '@/components/ui/PyramidMark.vue'
import Icon from '@/components/ui/Icon.vue'
import type { FeedbackMessage } from '@/api/feedback'
defineProps<{ messages: FeedbackMessage[] }>()
</script>

<template>
  <ul class="list" aria-label="Μηνύματα για σήμερα">
    <li v-for="(m, i) in messages" :key="m.id" class="msg" :class="i === 0 ? 'msg--surface' : 'msg--outline'">
      <PyramidMark v-if="i === 0" :height="28" />
      <Icon v-else name="sparkle" :size="22" />
      <p class="t-body">{{ m.text }}</p>
    </li>
  </ul>
</template>

<style scoped>
.list { display: flex; flex-direction: column; gap: 10px; }
.msg { display: flex; align-items: flex-start; gap: 12px; border-radius: 16px; padding: 14px 16px; }
.msg--surface { background: var(--color-surface); }
.msg--outline { border: 1.5px solid var(--color-ink); }
.msg > :first-child { flex: none; margin-top: 2px; }
</style>
