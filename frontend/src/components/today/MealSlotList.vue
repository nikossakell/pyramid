<script setup lang="ts">
// C11 MealSlotList (ΚΡΑΤΑ): 6 θέσεις. Γεμάτη = surface + πράσινο σημάδι + ονόματα τροφίμων → λεπτομέρεια γεύματος (S12).
// Κενή = διακεκομμένο περίγραμμα + «+» → S05 με προεπιλεγμένη θέση. «σε αναμονή αποστολής» για την ουρά offline (Στάδιο C).
import { computed } from 'vue'
import { RouterLink } from 'vue-router'
import Icon from '@/components/ui/Icon.vue'
import { MEAL_SLOTS, type Meal, type MealSlot } from '@/api/meals'

const props = defineProps<{ meals: Meal[]; pending?: { slot: MealSlot; names: string[] }[] }>()

const rows = computed(() => MEAL_SLOTS.map(({ slot, label }) => {
  const filled = props.meals.filter((m) => m.meal_slot === slot)
  const queued = (props.pending ?? []).filter((p) => p.slot === slot)
  const names = [...filled.flatMap((m) => m.items.map((i) => i.name_el)), ...queued.flatMap((p) => p.names)]
  return { slot, label, meal: filled[0] ?? null, queued: queued.length > 0 && filled.length === 0, summary: names.join(', ') }
}))
</script>

<template>
  <section aria-label="Τα γεύματα σήμερα" class="slots">
    <h2 class="t-caption head">Τα γεύματα σήμερα</h2>
    <ul class="list">
      <li v-for="r in rows" :key="r.slot">
        <RouterLink v-if="r.meal" :to="{ name: 'meal', params: { id: r.meal.meal_id } }" class="row row--filled pressable">
          <span class="mark mark--done"><Icon name="check" :size="16" :stroke="3" /></span>
          <span class="txt"><span class="label">{{ r.label }}</span><span class="sub">{{ r.summary }}</span></span>
          <Icon name="chevron" :size="18" />
        </RouterLink>
        <div v-else-if="r.queued" class="row row--filled">
          <span class="mark mark--queued"><Icon name="clock" :size="16" /></span>
          <span class="txt"><span class="label">{{ r.label }}</span><span class="sub">{{ r.summary }} · σε αναμονή αποστολής</span></span>
        </div>
        <RouterLink v-else :to="{ name: 'log', query: { slot: r.slot } }" class="row row--empty pressable">
          <span class="mark mark--empty"><Icon name="plus" :size="16" :stroke="2.4" /></span>
          <span class="txt"><span class="label">{{ r.label }}</span><span class="sub">Πάτα για καταγραφή</span></span>
        </RouterLink>
      </li>
    </ul>
  </section>
</template>

<style scoped>
.slots { display: flex; flex-direction: column; gap: 8px; }
.head { font-weight: 700; font-size: calc(15px * var(--text-scale)); }
.list { display: flex; flex-direction: column; gap: 8px; }
.row { display: flex; align-items: center; gap: 12px; border-radius: 16px; padding: 8px 12px; min-height: 56px; text-decoration: none; color: var(--color-text); }
.row--filled { background: var(--color-surface); }
.row--empty { border: 1.5px dashed var(--color-absent); }
.mark { width: 30px; height: 30px; border-radius: 999px; display: inline-flex; align-items: center; justify-content: center; flex: none; }
.mark--done { background: var(--color-positive); color: #fff; }
.mark--queued { border: 2px solid var(--color-ink); }
.mark--empty { border: 1.5px solid var(--color-absent); }
.txt { flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 1px; }
.label { font-weight: 600; font-size: calc(15px * var(--text-scale)); }
.sub { color: var(--color-text-muted); font-size: calc(13px * var(--text-scale)); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
