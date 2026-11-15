<script setup lang="ts">
// C17 CardTeaser (ΚΡΑΤΑ): «Έχεις κάρτα να ανοίξεις» (→ Κάρτες· το M03 είναι εκτός φάσης), «Νέες κάρτες αύριο το πρωί»
// όταν η σημερινή άνοιξε, «Δες τη συλλογή σου» όταν δεν υπάρχει κάρτα σήμερα. Χωρίς μήνυμα σφάλματος.
import { RouterLink } from 'vue-router'
import Icon from '@/components/ui/Icon.vue'
defineProps<{ unopened: number; cardToday: boolean }>()
</script>

<template>
  <RouterLink v-if="unopened > 0" to="/cards" class="teaser teaser--new pressable">
    <span class="stack" aria-hidden="true"><span class="c c--back" /><span class="c c--front" /></span>
    <span class="txt">
      <span class="t1">{{ unopened === 1 ? 'Έχεις 1 κάρτα να ανοίξεις' : `Έχεις ${unopened} κάρτες να ανοίξεις` }}</span>
      <span class="t2">Πάτα για να τη δεις</span>
    </span>
    <Icon name="chevron" :size="20" />
  </RouterLink>
  <div v-else-if="cardToday" class="teaser teaser--quiet">
    <span class="ico"><Icon name="clock" :size="22" /></span>
    <span class="txt"><span class="t1">Νέες κάρτες αύριο το πρωί</span><span class="t2 muted">Οι κάρτες μοιράζονται μία φορά τη μέρα</span></span>
  </div>
  <RouterLink v-else to="/cards" class="teaser teaser--quiet pressable">
    <span class="t1 grow">Δες τη συλλογή σου</span>
    <Icon name="chevron" :size="20" />
  </RouterLink>
</template>

<style scoped>
.teaser { display: flex; align-items: center; gap: 14px; border-radius: 18px; padding: 12px 16px; text-decoration: none; color: var(--color-text); min-height: 60px; }
.teaser--new { background: var(--color-secondary); color: #fff; }
.teaser--quiet { border: 1.5px solid var(--color-line); }
.stack { position: relative; width: 40px; height: 52px; flex: none; }
.c { position: absolute; width: 32px; height: 46px; border-radius: 7px; }
.c--back { left: 8px; top: 0; border: 2px solid #fff; }
.c--front { left: 0; top: 6px; background: #fff; }
.ico { width: 40px; height: 40px; border-radius: 12px; background: var(--color-surface); display: flex; align-items: center; justify-content: center; flex: none; }
.txt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 2px; }
.t1 { font-weight: 700; font-size: calc(16px * var(--text-scale)); }
.t2 { font-size: calc(14px * var(--text-scale)); }
.grow { flex: 1; font-weight: 600; }
</style>
