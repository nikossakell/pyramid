<script setup lang="ts">
// S12 Ιστορικό (ΑΛΛΑΞΕ): χωρίς γραφήματα θρεπτικών. Προβολή Ημέρα / Εβδομάδα, κενή μέρα ουδέτερη (ποτέ κόκκινο),
// ένδειξη «ολοκληρωμένη μέρα» όταν δηλώθηκε (mockups_delta §1), κενό ιστορικό → C26. API: GET /meals, GET /days.
import { computed, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import BottomNav from '@/components/ui/BottomNav.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import Icon from '@/components/ui/Icon.vue'
import { ApiError } from '@/api/client'
import { slotLabel } from '@/api/meals'
import { addDays, longDate, weekdayName, weekStart } from '@/lib/dates'
import { useMealsStore } from '@/stores/meals'
import { useQueueStore } from '@/stores/queue'
import { useUiStore } from '@/stores/ui'

const meals = useMealsStore()
const queue = useQueueStore()
const ui = useUiStore()

const view = ref<'day' | 'week'>('week')
const anchor = ref(meals.today)                       // ημέρα (προβολή Ημέρα) ή οποιαδήποτε ημέρα της εβδομάδας
const loading = ref(false)

const start = computed(() => (view.value === 'week' ? weekStart(anchor.value) : anchor.value))
const end = computed(() => (view.value === 'week' ? addDays(start.value, 6) : anchor.value))
const canForward = computed(() => end.value < meals.today)
const thisWeek = computed(() => weekStart(anchor.value) === weekStart(meals.today))
const rangeLabel = computed(() => {
  if (view.value === 'day') return anchor.value === meals.today ? 'Σήμερα' : longDate(anchor.value)
  if (thisWeek.value) return 'Αυτή η εβδομάδα'
  return weekStart(anchor.value) === weekStart(addDays(meals.today, -7)) ? 'Προηγούμενη εβδομάδα' : `${longDate(start.value)} – ${longDate(end.value)}`
})

const days = computed(() => {
  const out = []
  for (let iso = start.value; iso <= end.value && iso <= meals.today; iso = addDays(iso, 1)) {
    const list = [...meals.mealsOn(iso)].sort((a, b) => (a.created_at < b.created_at ? -1 : 1))
    const pending = queue.pending.filter((p) => p.day === iso)
    const codes = new Set<string>()
    for (const m of list) for (const i of m.items) if (i.food_group) codes.add(i.food_group)
    out.push({ iso, meals: list, pending, groups: meals.shownGroups.filter((g) => codes.has(g.code)), completed: meals.dayCompleted(iso) })
  }
  return out.reverse()                                 // η πιο πρόσφατη πρώτη
})
const empty = computed(() => meals.loadedAt !== null && meals.meals.length === 0 && !queue.pending.length)

async function load(): Promise<void> {
  loading.value = true
  try {
    await meals.loadRange(start.value, end.value < meals.today ? end.value : meals.today)
  } catch (e) {
    if (!(e instanceof ApiError && (e.status === 0 || e.status === 401 || e.status === 403))) ui.toast('Δεν φορτώθηκε το ιστορικό. Δοκίμασε ξανά σε λίγο.', 'error')
  } finally {
    loading.value = false
  }
}
function move(n: number): void { anchor.value = addDays(anchor.value, view.value === 'week' ? 7 * n : n) }
function dayTitle(iso: string): string { return iso === meals.today ? `${weekdayName(iso)} · σήμερα` : view.value === 'week' ? weekdayName(iso) : longDate(iso) }

onMounted(load)
watch([start, end], load)
watch(() => ui.online, (on) => { if (on) load() })
</script>

<template>
  <div class="screen">
    <TopBar title="Ιστορικό" />
    <main class="screen__body body">
      <div class="tabs" role="tablist" aria-label="Προβολή">
        <button type="button" role="tab" class="tab" :class="{ 'tab--on': view === 'day' }" :aria-selected="view === 'day'" @click="view = 'day'">Ημέρα</button>
        <button type="button" role="tab" class="tab" :class="{ 'tab--on': view === 'week' }" :aria-selected="view === 'week'" @click="view = 'week'">Εβδομάδα</button>
      </div>
      <div class="nav">
        <button type="button" class="navbtn" :aria-label="view === 'week' ? 'Προηγούμενη εβδομάδα' : 'Προηγούμενη ημέρα'" @click="move(-1)"><Icon name="back" :size="22" :stroke="2.4" /></button>
        <span class="range">{{ rangeLabel }}</span>
        <button type="button" class="navbtn" :disabled="!canForward" :aria-label="view === 'week' ? 'Επόμενη εβδομάδα' : 'Επόμενη ημέρα'" @click="move(1)"><Icon name="chevron" :size="22" :stroke="2.4" /></button>
      </div>

      <EmptyState v-if="empty" icon="history" text="Δεν έχεις καταγράψει κάτι ακόμα. Ό,τι καταγράφεις θα φαίνεται εδώ." />

      <template v-else>
        <section v-for="d in days" :key="d.iso" class="day" :class="{ 'day--empty': !d.meals.length && !d.pending.length }" :aria-label="longDate(d.iso)">
          <div class="dayhead">
            <span class="daytitle">{{ dayTitle(d.iso) }}</span>
            <span v-if="d.completed" class="done"><Icon name="check" :size="12" :stroke="3" />ολοκληρωμένη μέρα</span>
            <span v-if="d.groups.length" class="gicons" :aria-label="`Ομάδες: ${d.groups.map((g) => g.label_el.toLowerCase()).join(', ')}`">
              <span v-for="g in d.groups" :key="g.code" class="gico"><Icon :name="g.code" :size="16" :stroke="2" /></span>
            </span>
          </div>
          <template v-if="d.meals.length || d.pending.length">
            <RouterLink v-for="m in d.meals" :key="m.meal_id" :to="{ name: 'meal', params: { id: m.meal_id } }" class="meal pressable">
              <span class="slot">{{ slotLabel(m.meal_slot) }}</span>
              <span class="names muted">{{ m.items.map((i) => i.name_el).join(', ') }}</span>
              <Icon name="chevron" :size="16" />
            </RouterLink>
            <div v-for="(p, i) in d.pending" :key="i" class="meal">
              <span class="slot">{{ slotLabel(p.slot) }}</span>
              <span class="names muted">{{ p.names.join(', ') }} · σε αναμονή αποστολής</span>
            </div>
          </template>
          <span v-else class="t-label muted">Καμία καταγραφή</span>
        </section>
      </template>
    </main>
    <BottomNav active="history" />
  </div>
</template>

<style scoped>
.body { gap: 14px; padding: 8px 16px 16px; }
.tabs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); background: var(--color-surface); border-radius: 14px; padding: 4px; }
.tab { height: 40px; border: 0; border-radius: 10px; background: transparent; color: inherit; font-size: calc(15px * var(--text-scale)); font-weight: 500; }
.tab--on { background: var(--color-bg); font-weight: 700; box-shadow: var(--shadow-card); }
.nav { display: flex; align-items: center; justify-content: space-between; }
.navbtn { width: 44px; height: 44px; border: 0; background: transparent; color: inherit; border-radius: 999px; display: flex; align-items: center; justify-content: center; }
.navbtn:disabled { color: var(--color-absent); }
.range { font-weight: 700; font-size: calc(16px * var(--text-scale)); }
.day { border: 1px solid var(--color-line); border-radius: 18px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.day--empty { background: var(--color-surface); border-color: transparent; }
.dayhead { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.daytitle { font-weight: 700; font-size: calc(16px * var(--text-scale)); flex: 1; }
.done { display: inline-flex; align-items: center; gap: 4px; font-size: calc(12px * var(--text-scale)); font-weight: 600; color: var(--color-text-muted); border: 1px solid var(--color-line); border-radius: 999px; padding: 2px 8px; }
.gicons { display: flex; gap: 4px; }
.gico { width: 26px; height: 26px; border-radius: 8px; background: var(--color-positive); color: #fff; display: inline-flex; align-items: center; justify-content: center; }
.meal { display: flex; align-items: center; gap: 10px; min-height: 44px; text-decoration: none; color: inherit; }
.slot { width: 104px; flex: none; font-weight: 600; font-size: calc(14px * var(--text-scale)); }
.names { flex: 1; min-width: 0; font-size: calc(14px * var(--text-scale)); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
</style>
