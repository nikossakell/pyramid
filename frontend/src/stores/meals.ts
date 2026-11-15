/**
 * Δεδομένα του «Σήμερα» (S04) και του Ιστορικού: γεύματα εβδομάδας, ημέρες, ομάδες τροφίμων, ανατροφοδότηση, κάρτες.
 * Η τελευταία επιτυχημένη φόρτωση μένει σε localStorage ώστε εκτός σύνδεσης το παιδί να «βλέπει ό,τι είναι αποθηκευμένο
 * στο κινητό» (S04δ). Μόνο ονόματα τροφίμων και κωδικοί· ποτέ εικόνα, ποτέ κλειδί. Καθαρίζεται στην αποσύνδεση.
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, OFFLINE } from '@/api/client'
import { completeDay as apiCompleteDay, listDays, listMeals, type Day, type Meal } from '@/api/meals'
import { getFeedbackToday, type Feedback } from '@/api/feedback'
import { getFoodGroups, type FoodGroup } from '@/api/foods'
import { listCards, type Card } from '@/api/cards'
import { addDays, todayIso, weekStart } from '@/lib/dates'

const CACHE_KEY = 'pyramid.cache.v1'
type Cache = { savedOn: string; meals: Meal[]; days: Day[]; groups: FoodGroup[]; feedback: Feedback | null; cards: Card[] }

function readCache(): Cache | null {
  try { return JSON.parse(localStorage.getItem(CACHE_KEY) ?? 'null') } catch { return null }
}
function writeCache(c: Cache): void {
  try { localStorage.setItem(CACHE_KEY, JSON.stringify(c)) } catch { /* private mode */ }
}

export const useMealsStore = defineStore('meals', () => {
  const cached = readCache()
  const meals = ref<Meal[]>(cached?.meals ?? [])          // εύρος: Δευτέρα της εβδομάδας → σήμερα (+ ό,τι ζητηθεί για S12)
  const days = ref<Day[]>(cached?.days ?? [])
  const groups = ref<FoodGroup[]>(cached?.groups ?? [])
  const feedback = ref<Feedback | null>(cached?.feedback ?? null)
  const cards = ref<Card[]>(cached?.cards ?? [])
  const loading = ref(false)
  const loadedAt = ref<number | null>(null)
  const fromCache = ref(!!cached)
  const today = ref(todayIso())

  const shownGroups = computed(() => groups.value.filter((g) => g.shown).sort((a, b) => a.sort - b.sort))
  const mealsToday = computed(() => meals.value.filter((m) => m.eaten_on === today.value))
  const todayCompleted = computed(() => days.value.find((d) => d.day === today.value)?.completed ?? false)
  const unopenedCards = computed(() => cards.value.filter((c) => !c.opened).length)
  const cardToday = computed(() => cards.value.some((c) => c.day === today.value))
  /** Ομάδες (shown) που είχε σήμερα: από το /feedback/today και, για offline, από τα ίδια τα γεύματα. */
  const groupsToday = computed(() => {
    const set = new Set(feedback.value?.food_groups_today ?? [])
    for (const m of mealsToday.value) for (const i of m.items) if (i.food_group) set.add(i.food_group)
    return shownGroups.value.filter((g) => set.has(g.code)).map((g) => g.code)
  })

  function mealsOn(iso: string): Meal[] { return meals.value.filter((m) => m.eaten_on === iso) }
  function dayCompleted(iso: string): boolean { return days.value.find((d) => d.day === iso)?.completed ?? false }

  function persist(): void {
    writeCache({ savedOn: today.value, meals: meals.value, days: days.value, groups: groups.value, feedback: feedback.value, cards: cards.value })
  }

  /** Φόρτωση για το S04: εβδομάδα γευμάτων, ημέρες, ομάδες, ανατροφοδότηση, κάρτες. Επιστρέφει false αν απέτυχε (offline κ.λπ.). */
  async function loadToday(): Promise<boolean> {
    today.value = todayIso()
    const from = weekStart(today.value)
    loading.value = true
    try {
      const [m, d, f, c, g] = await Promise.all([
        listMeals(from, today.value),
        listDays(from, today.value),
        getFeedbackToday(),
        listCards(),
        groups.value.length ? Promise.resolve(groups.value) : getFoodGroups(),
      ])
      // Κρατάμε γεύματα εκτός εύρους (π.χ. παλιότερα για το S12) και αντικαθιστούμε το εύρος της εβδομάδας.
      meals.value = [...meals.value.filter((x) => x.eaten_on < from || x.eaten_on > today.value), ...m]
      days.value = [...days.value.filter((x) => x.day < from || x.day > today.value), ...d]
      feedback.value = f
      cards.value = c
      groups.value = g
      loadedAt.value = Date.now()
      fromCache.value = false
      persist()
      return true
    } catch (e) {
      if (e instanceof ApiError && e.status === OFFLINE) return false
      throw e
    } finally {
      loading.value = false
    }
  }

  /** Εύρος για το S12 (έως 31 ημέρες ανά κλήση στο backend). */
  async function loadRange(from: string, to: string): Promise<void> {
    const [m, d] = await Promise.all([listMeals(from, to), listDays(from, to)])
    meals.value = [...meals.value.filter((x) => x.eaten_on < from || x.eaten_on > to), ...m]
    days.value = [...days.value.filter((x) => x.day < from || x.day > to), ...d]
    if (!groups.value.length) groups.value = await getFoodGroups()
    persist()
  }

  async function completeToday(): Promise<void> {
    const res = await apiCompleteDay(today.value)
    days.value = [...days.value.filter((x) => x.day !== res.day), res]
    persist()
  }

  /** Μετά από επιβεβαίωση γεύματος (Στάδιο C): τοπική ενημέρωση και ξαναφόρτωμα ανατροφοδότησης. */
  function upsertMeal(meal: Meal): void {
    meals.value = [...meals.value.filter((m) => m.meal_id !== meal.meal_id), meal]
    persist()
  }
  function removeMeal(mealId: string): void {
    meals.value = meals.value.filter((m) => m.meal_id !== mealId)
    persist()
  }

  function clear(): void {
    meals.value = []; days.value = []; feedback.value = null; cards.value = []; loadedAt.value = null; fromCache.value = false
    try { localStorage.removeItem(CACHE_KEY) } catch { /* ignore */ }
  }

  return {
    meals, days, groups, feedback, cards, loading, loadedAt, fromCache, today,
    shownGroups, mealsToday, todayCompleted, unopenedCards, cardToday, groupsToday,
    mealsOn, dayCompleted, loadToday, loadRange, completeToday, upsertMeal, removeMeal, clear,
    yesterday: computed(() => addDays(today.value, -1)),
  }
})
