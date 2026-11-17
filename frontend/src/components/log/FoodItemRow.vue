<script setup lang="ts">
// C09 FoodItemRow (ΚΡΑΤΑ): όνομα, «πρόταση AI» / «πρόσθεσες εσύ», βεβαιότητα μόνο με λέξεις, αφαίρεση με αναίρεση,
// C10 μερίδα χωρίς προεπιλογή. Χωρίς αντιστοίχιση (food_id null): surface + έως 3 εναλλακτικές + «Ψάξ' το».
import Icon from '@/components/ui/Icon.vue'
import PortionSelector from './PortionSelector.vue'
import type { Alternative, MealSource, Portion } from '@/api/meals'
import type { DraftItem } from '@/stores/log'

defineProps<{ item: DraftItem; source: MealSource }>()
const emit = defineEmits<{ portion: [v: Portion]; remove: []; restore: []; alternative: [a: Alternative]; search: []; askPortion: [] }>()
</script>

<template>
  <div v-if="item.removed" class="row row--removed">
    <div class="txt"><span class="name muted">{{ item.name_el }}</span><span class="t-caption muted">Αφαιρέθηκε</span></div>
    <button type="button" class="undo" @click="emit('restore')">Αναίρεση</button>
  </div>

  <div v-else-if="item.food_id === null" class="row row--unresolved">
    <div class="head">
      <div class="txt">
        <span class="name">«{{ item.name_el }}»</span>
        <span class="t-label">Δεν το βρήκα. Ψάξ' το ή διάλεξε από αυτά:</span>
      </div>
      <button type="button" class="iconbtn" :aria-label="`Αφαίρεσε: ${item.name_el}`" @click="emit('remove')"><Icon name="x" :size="22" /></button>
    </div>
    <div class="alts">
      <button v-for="a in item.alternatives" :key="a.food_id" type="button" class="chip chip--outline" @click="emit('alternative', a)">{{ a.name_el }}</button>
      <button type="button" class="chip searchchip" @click="emit('search')"><Icon name="search" :size="16" />Ψάξ' το</button>
    </div>
  </div>

  <div v-else class="row">
    <div class="head">
      <div class="txt">
        <span class="name">{{ item.name_el }}</span>
        <span class="meta">
          <span v-if="item.ai_suggested" class="tag tag--ai">πρόταση AI</span>
          <span v-else class="tag">πρόσθεσες εσύ</span>
          <span v-if="item.ai_suggested" class="t-caption muted">{{ source === 'text' ? 'από το κείμενό σου' : item.confidence_word }}</span>
        </span>
      </div>
      <button type="button" class="iconbtn" :aria-label="`Αφαίρεσε: ${item.name_el}`" @click="emit('remove')"><Icon name="x" :size="22" /></button>
    </div>
    <PortionSelector :model-value="item.portion" :label="`Μερίδα για ${item.name_el}`" @update:model-value="emit('portion', $event)" />
    <button v-if="item.portion === null" type="button" class="ask" @click="emit('askPortion')">Πόσο μεγάλο ήταν;</button>
  </div>
</template>

<style scoped>
.row { border: 1px solid var(--color-line); border-radius: 18px; padding: 12px 6px 12px 14px; display: flex; flex-direction: column; gap: 10px; }
.row--removed { border-style: dashed; border-color: var(--color-absent); flex-direction: row; align-items: center; justify-content: space-between; padding: 12px 8px 12px 16px; }
.row--unresolved { background: var(--color-surface); border: 2px solid var(--color-ink); }
.head { display: flex; align-items: flex-start; justify-content: space-between; gap: 8px; }
.txt { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.name { font-weight: 600; font-size: calc(17px * var(--text-scale)); }
.meta { display: flex; align-items: center; gap: 6px; flex-wrap: wrap; }
.tag { font-size: calc(12px * var(--text-scale)); font-weight: 700; border-radius: 999px; border: 1.5px solid var(--color-ink); padding: 0 7px; line-height: 18px; }
.tag--ai { color: var(--color-secondary); border-color: var(--color-secondary); }
.iconbtn { width: 44px; height: 44px; border: 0; background: transparent; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; flex: none; color: inherit; }
.undo { height: 44px; border: 0; border-radius: 12px; background: var(--color-surface); font-weight: 700; font-size: calc(14px * var(--text-scale)); padding: 0 14px; }
.alts { display: flex; flex-wrap: wrap; gap: 8px; padding-right: 8px; }
.searchchip { border: 0; font-weight: 700; }
.ask { align-self: flex-start; border: 0; background: transparent; padding: 0 2px; font-weight: 600; font-size: calc(14px * var(--text-scale)); text-decoration: underline; min-height: 32px; }
/* expanded (S08): η μερίδα επιλέγεται inline από το segmented control· το M02 δεν χρειάζεται */
@media (min-width: 1024px) {
  .ask { display: none; }
  .row { padding: 14px 10px 14px 18px; }
}
</style>
