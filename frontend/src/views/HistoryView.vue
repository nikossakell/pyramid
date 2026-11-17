<script setup lang="ts">
// S12 Ιστορικό (ΑΛΛΑΞΕ): χωρίς γραφήματα θρεπτικών. Προβολή Ημέρα / Εβδομάδα, κενή μέρα ουδέτερη (ποτέ κόκκινο),
// ένδειξη «ολοκληρωμένη μέρα» όταν δηλώθηκε (mockups_delta §1), κενό ιστορικό → C26. API: GET /meals, GET /days.
// expanded: η εβδομάδα ως 7 στήλες (ημέρες) με τα γεύματα ως κάρτες μέσα στη στήλη· κλικ σε γεύμα → πάνελ λεπτομέρειας
// δεξιά (MealDetail) αντί για νέα σελίδα. Σε compact/medium μένει η σημερινή λίστα και η πλοήγηση στο S12β.
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import BottomNav from '@/components/ui/BottomNav.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import Icon from '@/components/ui/Icon.vue'
import MealDetail from '@/components/history/MealDetail.vue'
import { ApiError } from '@/api/client'
import { slotLabel, type Meal } from '@/api/meals'
import { addDays, longDate, weekdayName, weekStart } from '@/lib/dates'
import { useBreakpoint } from '@/composables/useBreakpoint'
import { useMealsStore } from '@/stores/meals'
import { useQueueStore } from '@/stores/queue'
import { useUiStore } from '@/stores/ui'

const meals = useMealsStore()
const queue = useQueueStore()
const ui = useUiStore()
const { isExpanded } = useBreakpoint()

const view = ref<'day' | 'week'>('week')
const anchor = ref(meals.today)                       // ημέρα (προβολή Ημέρα) ή οποιαδήποτε ημέρα της εβδομάδας
const loading = ref(false)
const selectedId = ref<string | null>(null)           // expanded: γεύμα στο πάνελ δεξιά

const start = computed(() => (view.value === 'week' ? weekStart(anchor.value) : anchor.value))
const end = computed(() => (view.value === 'week' ? addDays(start.value, 6) : anchor.value))
const canForward = computed(() => end.value < meals.today)
const thisWeek = computed(() => weekStart(anchor.value) === weekStart(meals.today))
const rangeLabel = computed(() => {
  if (view.value === 'day') return anchor.value === meals.today ? 'Σήμερα' : longDate(anchor.value)
  if (thisWeek.value) return 'Αυτή η εβδομάδα'
  return weekStart(anchor.value) === weekStart(addDays(meals.today, -7)) ? 'Προηγούμενη εβδομάδα' : `${longDate(start.value)} – ${longDate(end.value)}`
})

function dayInfo(iso: string) {
  const future = iso > meals.today
  const list = future ? [] : [...meals.mealsOn(iso)].sort((a, b) => (a.created_at < b.created_at ? -1 : 1))
  const pending = future ? [] : queue.pending.filter((p) => p.day === iso)
  const codes = new Set<string>()
  for (const m of list) for (const i of m.items) if (i.food_group) codes.add(i.food_group)
  return { iso, future, meals: list, pending, groups: meals.shownGroups.filter((g) => codes.has(g.code)), completed: !future && meals.dayCompleted(iso) }
}
const days = computed(() => {
  const out = []
  for (let iso = start.value; iso <= end.value && iso <= meals.today; iso = addDays(iso, 1)) out.push(dayInfo(iso))
  return out.reverse()                                 // η πιο πρόσφατη πρώτη
})
/** expanded, εβδομάδα: και οι 7 ημέρες με τη σειρά τους· οι μελλοντικές ουδέτερες. */
const columns = computed(() => Array.from({ length: 7 }, (_, i) => dayInfo(addDays(start.value, i))))
const empty = computed(() => meals.loadedAt !== null && meals.meals.length === 0 && !queue.pending.length)
const selectedMeal = computed<Meal | null>(() => meals.meals.find((m) => m.meal_id === selectedId.value) ?? null)
const weekGrid = computed(() => isExpanded.value && view.value === 'week' && !empty.value)

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
function colTitle(iso: string): string { return weekdayName(iso) }
/** Στήλη εβδομάδας: μόνο ημέρα και μήνας (ο τίτλος έχει ήδη την ημέρα της εβδομάδας). */
function colDate(iso: string): string { return new Date(`${iso}T12:00:00`).toLocaleDateString('el-GR', { day: 'numeric', month: 'short' }) }

onMounted(load)
watch([start, end], load)
watch(() => ui.online, (on) => { if (on) load() })
watch(selectedMeal, (m) => { if (!m) selectedId.value = null })
// 1024–1279 το πάνελ είναι κάτω από την εβδομάδα: φέρ' το στην οθόνη και δώσε του εστίαση (πληκτρολόγιο, αναγνώστες οθόνης)
const panelEl = ref<HTMLElement | null>(null)
watch(selectedId, async (id) => {
  if (!id || !panelEl.value) return
  await nextTick()
  if (window.innerWidth < 1280) panelEl.value.scrollIntoView({ block: 'start', behavior: ui.prefs.reduceMotion ? 'auto' : 'smooth' })
  panelEl.value.focus({ preventScroll: true })
})
</script>

<template>
  <div class="screen">
    <TopBar title="Ιστορικό" />
    <main class="screen__body body" :class="{ 'body--panel': isExpanded }">
      <div class="main">
        <div class="tabs" role="tablist" aria-label="Προβολή">
          <button type="button" role="tab" class="tab" :class="{ 'tab--on': view === 'day' }" :aria-selected="view === 'day'" @click="view = 'day'">Ημέρα</button>
          <button type="button" role="tab" class="tab" :class="{ 'tab--on': view === 'week' }" :aria-selected="view === 'week'" @click="view = 'week'">Εβδομάδα</button>
        </div>
        <div class="rangenav">
          <button type="button" class="navbtn" :aria-label="view === 'week' ? 'Προηγούμενη εβδομάδα' : 'Προηγούμενη ημέρα'" @click="move(-1)"><Icon name="back" :size="22" :stroke="2.4" /></button>
          <span class="range">{{ rangeLabel }}</span>
          <button type="button" class="navbtn" :disabled="!canForward" :aria-label="view === 'week' ? 'Επόμενη εβδομάδα' : 'Επόμενη ημέρα'" @click="move(1)"><Icon name="chevron" :size="22" :stroke="2.4" /></button>
        </div>

        <EmptyState v-if="empty" icon="history" text="Δεν έχεις καταγράψει κάτι ακόμα. Ό,τι καταγράφεις θα φαίνεται εδώ." />

        <!-- expanded, εβδομάδα: 7 στήλες -->
        <div v-else-if="weekGrid" class="week" role="list" aria-label="Ημέρες της εβδομάδας">
          <section v-for="d in columns" :key="d.iso" class="col" :class="{ 'col--today': d.iso === meals.today, 'col--future': d.future, 'col--empty': !d.future && !d.meals.length && !d.pending.length }" role="listitem" :aria-label="longDate(d.iso)">
            <div class="colhead">
              <span class="coltitle">{{ colTitle(d.iso) }}<span v-if="d.iso === meals.today" class="muted"> · σήμερα</span></span>
              <span class="t-caption muted">{{ colDate(d.iso) }}</span>
              <span v-if="d.completed" class="done"><Icon name="check" :size="12" :stroke="3" />ολοκληρωμένη μέρα</span>
              <span v-if="d.groups.length" class="gicons" :aria-label="`Ομάδες: ${d.groups.map((g) => g.label_el.toLowerCase()).join(', ')}`">
                <span v-for="g in d.groups" :key="g.code" class="gico"><Icon :name="g.code" :size="16" :stroke="2" /></span>
              </span>
            </div>
            <template v-if="d.meals.length || d.pending.length">
              <button v-for="m in d.meals" :key="m.meal_id" type="button" class="mealcard pressable" :class="{ 'mealcard--on': m.meal_id === selectedId }" :aria-pressed="m.meal_id === selectedId" @click="selectedId = m.meal_id">
                <span class="slot">{{ slotLabel(m.meal_slot) }}</span>
                <span class="cardnames muted">{{ m.items.map((i) => i.name_el).join(', ') }}</span>
              </button>
              <div v-for="(p, i) in d.pending" :key="i" class="mealcard mealcard--queued">
                <span class="slot">{{ slotLabel(p.slot) }}</span>
                <span class="cardnames muted">{{ p.names.join(', ') }} · σε αναμονή αποστολής</span>
              </div>
            </template>
            <span v-else-if="!d.future" class="t-caption muted">Καμία καταγραφή</span>
          </section>
        </div>

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
              <template v-for="m in d.meals" :key="m.meal_id">
                <button v-if="isExpanded" type="button" class="meal meal--btn pressable" :class="{ 'meal--on': m.meal_id === selectedId }" :aria-pressed="m.meal_id === selectedId" @click="selectedId = m.meal_id">
                  <span class="slot">{{ slotLabel(m.meal_slot) }}</span>
                  <span class="names muted">{{ m.items.map((i) => i.name_el).join(', ') }}</span>
                  <Icon name="chevron" :size="16" />
                </button>
                <RouterLink v-else :to="{ name: 'meal', params: { id: m.meal_id } }" class="meal pressable">
                  <span class="slot">{{ slotLabel(m.meal_slot) }}</span>
                  <span class="names muted">{{ m.items.map((i) => i.name_el).join(', ') }}</span>
                  <Icon name="chevron" :size="16" />
                </RouterLink>
              </template>
              <div v-for="(p, i) in d.pending" :key="i" class="meal">
                <span class="slot">{{ slotLabel(p.slot) }}</span>
                <span class="names muted">{{ p.names.join(', ') }} · σε αναμονή αποστολής</span>
              </div>
            </template>
            <span v-else class="t-label muted">Καμία καταγραφή</span>
          </section>
        </template>
      </div>

      <!-- expanded: πάνελ λεπτομέρειας δεξιά -->
      <aside v-if="isExpanded && !empty" ref="panelEl" class="panel" tabindex="-1" aria-label="Λεπτομέρεια γεύματος">
        <MealDetail v-if="selectedMeal" :key="selectedMeal.meal_id" :meal="selectedMeal" heading @deleted="selectedId = null" />
        <EmptyState v-else icon="history" text="Διάλεξε ένα γεύμα για να δεις τι είχε." />
      </aside>
    </main>
    <BottomNav active="history" />
  </div>
</template>

<style scoped>
.body { gap: 14px; padding: 8px 16px 16px; }
.main { display: contents; }
.tabs { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); background: var(--color-surface); border-radius: 14px; padding: 4px; }
.tab { height: 40px; border: 0; border-radius: 10px; background: transparent; color: inherit; font-size: calc(15px * var(--text-scale)); font-weight: 500; }
.tab--on { background: var(--color-bg); font-weight: 700; box-shadow: var(--shadow-card); }
/* όχι «.nav»: τα scoped styles πιάνουν και τη ρίζα του BottomNav (<nav class="nav">) */
.rangenav { display: flex; align-items: center; justify-content: space-between; }
.navbtn { width: 44px; height: 44px; border: 0; background: transparent; color: inherit; border-radius: 999px; display: flex; align-items: center; justify-content: center; }
.navbtn:disabled { color: var(--color-absent); }
.range { font-weight: 700; font-size: calc(16px * var(--text-scale)); }
.day { border: 1px solid var(--color-line); border-radius: 18px; padding: 14px; display: flex; flex-direction: column; gap: 10px; }
.day--empty { background: var(--color-surface); border-color: transparent; }
.dayhead { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.daytitle { font-weight: 700; font-size: calc(16px * var(--text-scale)); flex: 1; }
.done { display: inline-flex; align-items: center; gap: 4px; font-size: calc(12px * var(--text-scale)); font-weight: 600; color: var(--color-text-muted); border: 1px solid var(--color-line); border-radius: 999px; padding: 2px 8px; }
.gicons { display: flex; gap: 4px; flex-wrap: wrap; }
.gico { width: 26px; height: 26px; border-radius: 8px; background: var(--color-positive); color: #fff; display: inline-flex; align-items: center; justify-content: center; }
.meal { display: flex; align-items: center; gap: 10px; min-height: 44px; text-decoration: none; color: inherit; }
.meal--btn { width: 100%; border: 0; background: transparent; padding: 0; text-align: left; font: inherit; border-radius: 12px; }
.meal--on { background: var(--color-surface); }
.slot { width: 104px; flex: none; font-weight: 600; font-size: calc(14px * var(--text-scale)); }
.names { flex: 1; min-width: 0; font-size: calc(14px * var(--text-scale)); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }

/* expanded: η εβδομάδα ως 7 στήλες. 1024–1279: το πάνελ λεπτομέρειας κάτω από την εβδομάδα (αλλιώς οι 7 στήλες δεν χωρούν
   ονόματα)· ≥ 1280: αριστερά (8) εβδομάδα/ημέρα, δεξιά (4) sticky πάνελ. */
@media (min-width: 1024px) {
  .body--panel { display: grid; grid-template-columns: minmax(0, 1fr); gap: 24px; align-items: start; padding-bottom: 40px; }
  .main { display: flex; flex-direction: column; gap: 14px; min-width: 0; }
  .tabs { max-width: 320px; }
  .panel { scroll-margin-top: 16px; outline: none; border: 1px solid var(--color-line); border-radius: 20px; padding: 18px 16px; box-shadow: var(--shadow-card); background: var(--color-bg); }
  .week { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 8px; }
  .col { display: flex; flex-direction: column; gap: 8px; border: 1px solid var(--color-line); border-radius: 16px; padding: 10px 8px; min-height: 220px; min-width: 0; }
  .col--today { border-color: var(--color-ink); }
  .col--empty, .col--future { background: var(--color-surface); border-color: transparent; }
  .col--today.col--empty { border-color: var(--color-ink); }
  .colhead { display: flex; flex-direction: column; gap: 4px; padding-bottom: 6px; border-bottom: 1px solid var(--color-line); }
  .coltitle { font-weight: 700; font-size: calc(14px * var(--text-scale)); overflow-wrap: break-word; hyphens: auto; }
  .mealcard { display: flex; flex-direction: column; gap: 2px; width: 100%; border: 1px solid var(--color-line); border-radius: 12px; background: var(--color-bg); color: inherit; padding: 8px; text-align: left; font: inherit; min-height: 44px; }
  .mealcard--on { border: 2px solid var(--color-ink); background: var(--color-surface); }
  .mealcard--queued { border-style: dashed; }
  .mealcard .slot { width: auto; font-size: calc(13px * var(--text-scale)); overflow-wrap: break-word; hyphens: auto; }
  .cardnames { font-size: calc(12px * var(--text-scale)); line-height: 1.3; overflow-wrap: break-word; hyphens: auto; display: -webkit-box; -webkit-line-clamp: 3; -webkit-box-orient: vertical; overflow: hidden; }
  .mealcard--on .cardnames { -webkit-line-clamp: unset; }
}
@media (min-width: 1280px) {
  .body--panel { grid-template-columns: repeat(12, minmax(0, 1fr)); }
  .main { grid-column: 1 / span 8; }
  .panel { grid-column: 9 / span 4; position: sticky; top: 16px; }
}
</style>
