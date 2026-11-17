<script setup lang="ts">
// S04 Σήμερα (ΑΛΛΑΞΕ): χωρίς θρεπτικά (D2), χωρίς μετρητή σερί. Χαιρετισμός, C17 CardTeaser, C11 MealSlotList,
// C30 DayCompletePrompt, C12 FoodGroupSummary, C13 WeekDots, C14 FeedbackMessage. Εκτός σύνδεσης: ό,τι είναι
// αποθηκευμένο στο κινητό (S04δ)· η λωρίδα είναι η καθολική C28. API: /meals, /days, /feedback/today, /food-groups, /cards.
// Το /log (openLog) ανοίγει το S05 NewLogSheet· ?slot= προεπιλέγει τη θέση. M04 πριν την πρώτη χρήση της κάμερας.
import { computed, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import BottomNav from '@/components/ui/BottomNav.vue'
import MealSlotList from '@/components/today/MealSlotList.vue'
import FoodGroupSummary from '@/components/today/FoodGroupSummary.vue'
import WeekDots from '@/components/today/WeekDots.vue'
import FeedbackMessage from '@/components/today/FeedbackMessage.vue'
import CardTeaser from '@/components/today/CardTeaser.vue'
import DayCompletePrompt from '@/components/today/DayCompletePrompt.vue'
import NewLogSheet from '@/components/log/NewLogSheet.vue'
import CameraPermission from '@/components/modals/CameraPermission.vue'
import { ApiError } from '@/api/client'
import { MEAL_SLOTS, type MealSlot } from '@/api/meals'
import { greeting } from '@/lib/dates'
import { useMealsStore } from '@/stores/meals'
import { useMeStore } from '@/stores/me'
import { useQueueStore } from '@/stores/queue'
import { useUiStore } from '@/stores/ui'

const props = withDefaults(defineProps<{ openLog?: boolean }>(), { openLog: false })
const route = useRoute()
const router = useRouter()
const meals = useMealsStore()
const me = useMeStore()
const queue = useQueueStore()
const ui = useUiStore()

const M04_KEY = 'pyramid.camera_intro_seen'
const logOpen = ref(props.openLog)
const m04Open = ref(false)
const failed = ref(false)

const slotFromQuery = computed<MealSlot | null>(() => {
  const s = route.query.slot
  return typeof s === 'string' && MEAL_SLOTS.some((x) => x.slot === s) ? (s as MealSlot) : null
})
const pendingToday = computed(() => queue.pending.filter((p) => p.day === meals.today))
const hasMealsToday = computed(() => meals.mealsToday.length > 0 || pendingToday.value.length > 0)
const firstDay = computed(() => meals.loadedAt !== null && meals.meals.length === 0 && !meals.days.some((d) => d.completed) && !queue.pending.length)
/** C30: μετά το απογευματινό ή το βραδινό (ή αργά το απόγευμα), μόνο με τουλάχιστον ένα γεύμα στον server. */
const showDayPrompt = computed(() => meals.mealsToday.length > 0 && (
  meals.todayCompleted || new Date().getHours() >= 18 || meals.mealsToday.some((m) => m.meal_slot === 'afternoon_snack' || m.meal_slot === 'dinner')))

async function refresh(): Promise<void> {
  failed.value = false
  try {
    const ok = await meals.loadToday()
    if (!ok) failed.value = true                // offline: μένουν τα αποθηκευμένα
    if (!me.me) me.load().catch(() => {})
  } catch (e) {
    failed.value = true
    if (!(e instanceof ApiError && (e.status === 401 || e.status === 403))) ui.toast('Δεν φορτώθηκαν τα σημερινά. Δοκίμασε ξανά σε λίγο.', 'error')
  }
}

async function completeDay(): Promise<void> {
  try {
    await meals.completeToday()
  } catch (e) {
    if (e instanceof ApiError && e.status === 422) ui.toast('Κατέγραψε πρώτα ένα γεύμα για σήμερα.', 'info')
    else if (!(e instanceof ApiError && (e.status === 401 || e.status === 403))) ui.toast('Δεν στάλθηκε. Δοκίμασε ξανά σε λίγο.', 'error')
  }
}

function closeLog(): void {
  logOpen.value = false
  if (route.name === 'log') router.replace({ name: 'today' })
}
function seen(): boolean { try { return localStorage.getItem(M04_KEY) === '1' } catch { return false } }
function startCamera(): void {
  if (seen()) { router.push({ name: 'camera' }); return }
  logOpen.value = false
  m04Open.value = true
}
function acceptCamera(): void {
  try { localStorage.setItem(M04_KEY, '1') } catch { /* ignore */ }
  m04Open.value = false
  router.push({ name: 'camera' })
}

onMounted(refresh)
watch(() => ui.online, (on) => { if (on) refresh() })
watch(() => route.name, (n) => { logOpen.value = n === 'log' })
watch(() => queue.sentCount, () => refresh())
</script>

<template>
  <div class="screen">
    <TopBar title="Σήμερα" />
    <main class="screen__body body">
      <!-- Δύο στήλες μόνο σε expanded (8 + 4). Σε compact/medium οι wrappers είναι display: contents και το `order` δίνει
           τη σημερινή σειρά: χαιρετισμός, C17, C11, C30, C12, C14, C13. -->
      <div class="col col--main">
        <div class="g g--greet">
          <h2 class="t-display">{{ greeting() }}</h2>
          <p v-if="firstDay" class="t-body muted">Η πρώτη σου μέρα. Ξεκίνα με ό,τι φας πρώτο σήμερα.</p>
        </div>
        <MealSlotList class="g g--slots" :meals="meals.mealsToday" :pending="pendingToday" />
        <DayCompletePrompt v-if="showDayPrompt" class="g g--day" :completed="meals.todayCompleted" :day="meals.today" @confirm="completeDay" />
      </div>
      <div class="col col--side">
        <CardTeaser v-if="meals.loadedAt !== null || meals.fromCache" class="g g--teaser" :unopened="meals.unopenedCards" :card-today="meals.cardToday" />
        <FoodGroupSummary v-if="hasMealsToday && meals.shownGroups.length" class="g g--groups" :groups="meals.shownGroups" :present="meals.groupsToday" />
        <FeedbackMessage v-if="meals.feedback && meals.feedback.messages.length" class="g g--feedback" :messages="meals.feedback.messages" />
        <WeekDots v-if="meals.meals.length" class="g g--week" :meals="meals.meals" :today="meals.today" />
      </div>
    </main>
    <BottomNav active="today" :badge="meals.unopenedCards > 0" />

    <NewLogSheet v-if="logOpen" :open="logOpen" :slot="slotFromQuery" :from-slot="slotFromQuery !== null" @close="closeLog" @camera="startCamera" />
    <CameraPermission :open="m04Open" @continue="acceptCamera" @text="m04Open = false; router.push({ name: 'text' })" @close="m04Open = false; router.replace({ name: 'today' })" />
  </div>
</template>

<style scoped>
.body { gap: 16px; padding-bottom: 16px; }
/* compact/medium: οι στήλες «διαλύονται» και το order δίνει την ίδια σειρά με πριν */
.col { display: contents; }
.g--greet { order: 1; } .g--teaser { order: 2; } .g--slots { order: 3; } .g--day { order: 4; }
.g--groups { order: 5; } .g--feedback { order: 6; } .g--week { order: 7; }
/* expanded: πλέγμα 12 στηλών. Αριστερά (8): χαιρετισμός, C11 MealSlotList, C30. Δεξιά (4): C12, C14, C13, C17. */
@media (min-width: 1024px) {
  .body { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 24px; padding-top: 8px; padding-bottom: 40px; align-items: start; }
  .col { display: flex; flex-direction: column; gap: 20px; min-width: 0; }
  .col--main { grid-column: 1 / span 8; }
  .col--side { grid-column: 9 / span 4; }
  .g { order: 0; }
  .g--groups { order: 1; } .g--feedback { order: 2; } .g--week { order: 3; } .g--teaser { order: 4; }
}
</style>
