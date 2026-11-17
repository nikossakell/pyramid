<script setup lang="ts">
// S10 Ψάξε φαγητό (ΚΡΑΤΑ): ντετερμινιστική αναζήτηση στον server (GET /foods/search?q), «Πρόσφατα» από τα γεύματα
// (GET /meals), «Κατηγορίες» = οι ομάδες του /food-groups → κατάσταση δ (λίστα ομάδας με ?group=). Κάθε αποτέλεσμα δείχνει
// ΜΙΑ ομάδα (mockups_delta §4). Κανένα αποτέλεσμα → «Δεν το βρήκα» → S09. Η προσθήκη μπαίνει στο πρόχειρο (S08).
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'
import { ApiError, OFFLINE } from '@/api/client'
import { searchFoods, type Food } from '@/api/foods'
import { useLogStore } from '@/stores/log'
import { useMealsStore } from '@/stores/meals'
import { useUiStore } from '@/stores/ui'
import { useBreakpoint } from '@/composables/useBreakpoint'

const route = useRoute()
const router = useRouter()
const log = useLogStore()
const meals = useMealsStore()
const ui = useUiStore()
const { isExpanded } = useBreakpoint()

const q = ref('')
const results = ref<Food[]>([])
const group = ref<string | null>(null)          // κατάσταση δ
const searching = ref(false)
const offline = ref(false)
const fromConfirm = computed(() => route.query.from === 'confirm')
const replaceKey = computed(() => (typeof route.query.replace === 'string' ? Number(route.query.replace) : null))
let timer: ReturnType<typeof setTimeout> | null = null
let seq = 0

const groupLabel = (code: string | null) => meals.shownGroups.find((g) => g.code === code)?.label_el ?? meals.groups.find((g) => g.code === code)?.label_el ?? ''
const showResults = computed(() => q.value.trim().length > 0 || group.value !== null)
const noResults = computed(() => showResults.value && !searching.value && !offline.value && results.value.length === 0)
// expanded (master-detail): οι κατηγορίες μένουν πάντα αριστερά· τα «Πρόσφατα» στην κορυφή των αποτελεσμάτων όσο το πεδίο είναι κενό
const showCats = computed(() => !showResults.value || isExpanded.value)
const showRecent = computed(() => recent.value.length > 0 && (isExpanded.value ? q.value.trim().length === 0 : !showResults.value))

/** Πρόσφατα: μοναδικά τρόφιμα από τα τελευταία γεύματα, έως 5. */
const recent = computed<Food[]>(() => {
  const seen = new Set<string>()
  const out: Food[] = []
  for (const m of [...meals.meals].sort((a, b) => (a.created_at < b.created_at ? 1 : -1))) {
    for (const i of m.items) {
      if (seen.has(i.food_id) || !i.food_group) continue
      seen.add(i.food_id)
      out.push({ food_id: i.food_id, name_el: i.name_el, food_group: i.food_group })
      if (out.length >= 5) return out
    }
  }
  return out
})

async function run(): Promise<void> {
  const term = q.value.trim()
  if (!term && group.value === null) { results.value = []; return }
  const my = ++seq
  searching.value = true
  offline.value = false
  try {
    const r = await searchFoods(term, group.value ?? undefined)
    if (my === seq) results.value = r
  } catch (e) {
    if (my !== seq) return
    results.value = []
    if (e instanceof ApiError && e.status === OFFLINE) offline.value = true
    else if (!(e instanceof ApiError && (e.status === 401 || e.status === 403))) ui.toast('Κάτι πήγε στραβά. Δοκίμασε ξανά σε λίγο.', 'error')
  } finally {
    if (my === seq) searching.value = false
  }
}

watch(q, () => {
  group.value = null
  if (timer) clearTimeout(timer)
  timer = setTimeout(run, 250)
})
function openGroup(code: string): void { q.value = ''; group.value = code; run() }
function clear(): void { q.value = ''; group.value = null; results.value = [] }

function add(f: Food): void {
  if (replaceKey.value !== null && !log.hasFood(f.food_id)) {
    log.chooseAlternative(replaceKey.value, { food_id: f.food_id, name_el: f.name_el })
    const it = log.items.find((i) => i.key === replaceKey.value)
    if (it) it.food_group = f.food_group
    router.replace({ name: 'confirm' })
    return
  }
  if (!log.addFood(f)) ui.toast('Μέχρι εδώ για αυτό το γεύμα. Αποθήκευσέ το και ξεκίνα άλλο.', 'info')
}

function highlight(name: string): { pre: string; hit: string; post: string } {
  const t = q.value.trim().toLowerCase()
  const i = t ? name.toLowerCase().indexOf(t) : -1
  return i < 0 ? { pre: name, hit: '', post: '' } : { pre: name.slice(0, i), hit: name.slice(i, i + t.length), post: name.slice(i + t.length) }
}

onMounted(() => { if (!meals.groups.length) meals.loadToday().catch(() => {}) })
</script>

<template>
  <div class="screen">
    <TopBar title="Ψάξε φαγητό" back :avatar="false" :back-to="fromConfirm ? '/log/confirm' : '/log'" />
    <main class="screen__body body">
      <div class="searchbox">
        <label class="visually-hidden" for="food-q">Αναζήτηση φαγητού</label>
        <Icon name="search" :size="22" class="sicon" />
        <input id="food-q" v-model="q" class="sinput" type="search" placeholder="Γράψε ένα φαγητό" autocomplete="off" autocapitalize="off" spellcheck="false" enterkeyhint="search" />
        <button v-if="q || group" type="button" class="clearbtn" aria-label="Καθάρισε" @click="clear"><Icon name="x" :size="20" /></button>
      </div>

      <!-- Σε compact/medium οι wrappers είναι display: contents (ίδια ροή με πριν)· σε expanded: κατηγορίες αριστερά,
           αποτελέσματα σε πλέγμα δεξιά. -->
      <div class="results">
        <template v-if="showRecent">
          <span class="t-label bold">Πρόσφατα</span>
          <ul class="list">
            <li v-for="f in recent" :key="f.food_id" class="item">
              <span class="txt"><span class="name">{{ f.name_el }}</span><span class="t-caption muted">{{ groupLabel(f.food_group) }}</span></span>
              <button type="button" class="addbtn" :class="{ 'addbtn--on': log.hasFood(f.food_id) }" :aria-label="`Πρόσθεσε: ${f.name_el}`" @click="add(f)"><Icon :name="log.hasFood(f.food_id) ? 'check' : 'plus'" :size="20" :stroke="2.4" /></button>
            </li>
          </ul>
        </template>

        <template v-if="showResults">
          <span v-if="group" class="t-label bold">{{ groupLabel(group) }}</span>
          <div v-if="offline" class="banner" role="status"><Icon name="offline" :size="20" /><span>Χρειάζεται σύνδεση για την αναζήτηση.</span></div>
          <ul v-else-if="results.length" class="list" aria-label="Αποτελέσματα">
            <li v-for="f in results" :key="f.food_id" class="item">
              <span class="txt">
                <span class="name name--light">{{ highlight(f.name_el).pre }}<b>{{ highlight(f.name_el).hit }}</b>{{ highlight(f.name_el).post }}</span>
                <span class="t-caption muted">{{ groupLabel(f.food_group) }}</span>
              </span>
              <button type="button" class="addbtn" :class="{ 'addbtn--on': log.hasFood(f.food_id) }" :aria-label="`Πρόσθεσε: ${f.name_el}`" @click="add(f)"><Icon :name="log.hasFood(f.food_id) ? 'check' : 'plus'" :size="20" :stroke="2.4" /></button>
            </li>
          </ul>
          <div v-else-if="noResults" class="notfound">
            <Icon name="search" :size="40" :stroke="1.6" />
            <h2 class="t-title">Δεν το βρήκα</h2>
            <p class="t-body">Γράψ' το με δικά σου λόγια και θα προσπαθήσω να καταλάβω.</p>
            <AppButton :block="false" icon="pencil" @click="router.replace({ name: 'text' })">Γράψε τι έφαγες</AppButton>
          </div>
          <span v-if="results.length" class="t-caption muted">Τα αποτελέσματα έρχονται μόνο από τη βάση τροφίμων.</span>
        </template>
        <p v-else-if="isExpanded && !showRecent" class="t-body muted">Γράψε ένα φαγητό ή διάλεξε κατηγορία.</p>
      </div>

      <aside v-if="showCats" class="side" aria-label="Κατηγορίες">
        <span class="t-label bold">Κατηγορίες</span>
        <div class="cats">
          <button v-for="g in meals.shownGroups" :key="g.code" type="button" class="cat pressable" :class="{ 'cat--on': group === g.code }" :aria-current="group === g.code ? 'true' : undefined" @click="openGroup(g.code)"><Icon :name="g.code" :size="22" />{{ g.label_el }}</button>
        </div>
      </aside>
    </main>
    <footer v-if="log.active.length" class="screen__footer">
      <AppButton @click="router.replace({ name: 'confirm' })">{{ fromConfirm ? 'Πίσω στην επιβεβαίωση' : 'Συνέχεια' }}</AppButton>
    </footer>
  </div>
</template>

<style scoped>
.body { gap: 14px; padding: 8px 16px 16px; }
.searchbox { position: relative; }
.sicon { position: absolute; left: 14px; top: 50%; transform: translateY(-50%); }
.sinput { width: 100%; height: 52px; border-radius: 16px; border: 2px solid var(--color-ink); padding: 0 52px 0 46px; font-size: calc(17px * var(--text-scale)); background: var(--color-bg); -webkit-appearance: none; }
.sinput:focus { outline: none; }
.clearbtn { position: absolute; right: 4px; top: 4px; width: 44px; height: 44px; border: 0; background: transparent; border-radius: 999px; color: inherit; display: flex; align-items: center; justify-content: center; }
.bold { font-weight: 700; }
.list { display: flex; flex-direction: column; }
.item { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 60px; border-bottom: 1px solid var(--color-line); padding: 6px 0; }
.txt { display: flex; flex-direction: column; gap: 2px; min-width: 0; }
.name { font-weight: 600; font-size: calc(16px * var(--text-scale)); }
.name--light { font-weight: 400; }
.addbtn { width: 44px; height: 44px; border-radius: 999px; border: 1.5px solid var(--color-ink); background: var(--color-bg); color: inherit; display: flex; align-items: center; justify-content: center; flex: none; }
.addbtn--on { background: var(--color-primary); border-color: var(--color-primary); color: #000; }
.cats { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
.cat { min-height: 52px; border: 0; border-radius: 14px; background: var(--color-surface); color: inherit; font-weight: 600; font-size: calc(15px * var(--text-scale)); display: flex; align-items: center; gap: 10px; padding: 0 12px; text-align: left; }
.notfound { display: flex; flex-direction: column; align-items: center; text-align: center; gap: 14px; padding: 24px 12px; }
.results, .side { display: contents; }
.cat--on { background: var(--color-ink); color: var(--color-on-ink); }
/* expanded: master-detail. Αριστερά οι κατηγορίες (λίστα), δεξιά το πεδίο και τα αποτελέσματα σε πλέγμα 2–3 στηλών. */
@media (min-width: 1024px) {
  .body { display: grid; grid-template-columns: 260px minmax(0, 1fr); grid-template-areas: 'side search' 'side results'; grid-template-rows: auto 1fr; gap: 16px 32px; align-items: start; padding-bottom: 40px; }
  .searchbox { grid-area: search; }
  .side { grid-area: side; display: flex; flex-direction: column; gap: 10px; position: sticky; top: 16px; }
  .cats { display: flex; flex-direction: column; gap: 6px; }
  .cat { min-height: 48px; background: transparent; }
  .cat--on { background: var(--color-ink); }
  @media (hover: hover) { .cat:not(.cat--on):hover { background: var(--color-surface); filter: none; } }
  .results { grid-area: results; display: flex; flex-direction: column; gap: 14px; min-width: 0; }
  .list { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
  .item { border: 1px solid var(--color-line); border-radius: 16px; padding: 8px 8px 8px 14px; min-height: 64px; }
  .notfound { max-width: 480px; }
}
</style>
