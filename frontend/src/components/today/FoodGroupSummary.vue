<script setup lang="ts">
// C12 FoodGroupSummary (ΑΛΛΑΞΕ): οι ομάδες (shown=true) από το /food-groups σε πλέγμα 3 στηλών (9 ομάδες χωρούν στα 390 px,
// mockups_delta §4). Παρούσα = πράσινο γέμισμα + σημάδι + έντονη ετικέτα· απούσα = ουδέτερο γκρι, ποτέ κόκκινο.
// Χωρίς ποσότητες ή ποσοστά (R1). Η πρόταση είναι [*πρότυπο] μέχρι την έγκριση του διαιτολόγου.
import { computed } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import type { FoodGroup } from '@/api/foods'

const props = defineProps<{ groups: FoodGroup[]; present: string[] }>()

const presentLabels = computed(() => props.groups.filter((g) => props.present.includes(g.code)).map((g) => g.label_el.toLowerCase()))
const sentence = computed(() => {
  const l = presentLabels.value
  if (l.length === 0) return 'Οι ομάδες τροφίμων θα εμφανιστούν εδώ μόλις καταγράψεις κάτι.'
  if (l.length === 1) return `Σήμερα είχες ${l[0]}.`
  if (l.length <= 3) return `Σήμερα είχες ${l.slice(0, -1).join(', ')} και ${l[l.length - 1]}.`
  return `Σήμερα είχες ${l.slice(0, 3).join(', ')} και άλλα.`
})
</script>

<template>
  <section aria-label="Ομάδες τροφίμων σήμερα" class="card box">
    <h2 class="t-caption head">Ομάδες τροφίμων σήμερα</h2>
    <ul class="grid">
      <li v-for="g in groups" :key="g.code" class="cell" :class="{ 'cell--on': present.includes(g.code) }">
        <span class="ico">
          <Icon :name="g.code" :size="26" :stroke="1.9" />
          <span v-if="present.includes(g.code)" class="tick"><Icon name="check" :size="11" :stroke="3.2" /></span>
        </span>
        <span class="lbl">{{ g.label_el }}</span>
      </li>
    </ul>
    <p class="sentence">{{ sentence }} <span class="muted t-caption">[*πρότυπο]</span></p>
  </section>
</template>

<style scoped>
.box { border-radius: 20px; padding: 14px 12px; display: flex; flex-direction: column; gap: 12px; }
.head { font-weight: 700; font-size: calc(15px * var(--text-scale)); padding: 0 4px; }
.grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px 4px; }
.cell { display: flex; flex-direction: column; align-items: center; gap: 5px; text-align: center; }
.ico { position: relative; width: 52px; height: 52px; border-radius: 16px; display: flex; align-items: center; justify-content: center; border: 1.5px dashed var(--color-absent); color: var(--color-absent); }
.cell--on .ico { background: var(--color-positive); color: #fff; border: 0; }
.tick { position: absolute; right: -4px; bottom: -4px; width: 20px; height: 20px; border-radius: 999px; background: var(--color-ink); color: var(--color-on-ink); border: 2px solid var(--color-bg); display: flex; align-items: center; justify-content: center; }
.lbl { font-size: calc(13px * var(--text-scale)); line-height: 1.25; color: var(--color-text-muted); hyphens: auto; }
.cell--on .lbl { color: var(--color-text); font-weight: 600; }
.sentence { font-size: calc(15px * var(--text-scale)); line-height: 1.4; padding: 0 4px; }
</style>
