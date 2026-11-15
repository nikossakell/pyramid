/**
 * Πρόχειρη καταγραφή (S05 → S06/S09/S10 → S08 → S11). ΜΟΝΟ στη μνήμη: η εικόνα (Blob), το κείμενο του παιδιού και οι
 * προτάσεις δεν γράφονται πουθενά. Τίποτα δεν αποθηκεύεται στον server πριν το «Σωστό, αποθήκευσε» (R5).
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { MAX_ITEMS_PER_MEAL, type Alternative, type ConfirmBody, type MealSlot, type MealSource, type Portion, type Suggestion } from '@/api/meals'
import type { Food } from '@/api/foods'
import { todayIso } from '@/lib/dates'
import { uuid } from '@/lib/uuid'

export type DraftItem = {
  key: number
  food_id: string | null                 // null = δεν αντιστοιχίστηκε (S08β)
  name_el: string
  food_group: string | null              // γνωστό από την αναζήτηση· για το S11 εκτός σύνδεσης
  portion: Portion | null                // χωρίς προεπιλογή (mockups_delta §5)
  ai_suggested: boolean
  confidence_word: 'σίγουρο' | 'ίσως' | null
  alternatives: Alternative[]
  removed: boolean                       // «Αφαιρέθηκε · Αναίρεση»
}

/** Προεπιλεγμένη θέση γεύματος από την ώρα (S05α). */
export function slotForNow(now = new Date()): MealSlot {
  const h = now.getHours()
  if (h < 10) return 'breakfast'
  if (h < 12) return 'morning_snack'
  if (h < 16) return 'lunch'
  if (h < 19) return 'afternoon_snack'
  if (h < 23) return 'dinner'
  return 'snack'
}

export const useLogStore = defineStore('log', () => {
  const slot = ref<MealSlot>(slotForNow())
  const eatenOn = ref(todayIso())
  const source = ref<MealSource>('manual')
  const analysisId = ref<string | null>(null)
  const clientMealId = ref(uuid())
  const items = ref<DraftItem[]>([])
  const text = ref('')                               // S09: «Το κείμενό σου κρατήθηκε» (μόνο μνήμη)
  const image = ref<Blob | null>(null)               // S06 → S07, μετά null
  let nextKey = 1

  const active = computed(() => items.value.filter((i) => !i.removed))
  const unresolved = computed(() => active.value.filter((i) => i.food_id === null))
  const withoutPortion = computed(() => active.value.filter((i) => i.food_id !== null && i.portion === null))
  const canSave = computed(() => active.value.length > 0 && unresolved.value.length === 0 && withoutPortion.value.length === 0)
  const isFull = computed(() => active.value.length >= MAX_ITEMS_PER_MEAL)

  function start(s?: MealSlot): void {
    slot.value = s ?? slotForNow()
    eatenOn.value = todayIso()
    source.value = 'manual'
    analysisId.value = null
    clientMealId.value = uuid()
    items.value = []
    text.value = ''
    image.value = null
  }

  function setImage(blob: Blob | null): void { image.value = blob }

  /** Προτάσεις από φωτογραφία ή κείμενο → γραμμές του S08. Αντικαθιστά τις προτάσεις AI, κρατά ό,τι πρόσθεσε το παιδί. */
  function applySuggestions(src: 'camera' | 'text', analysis: string, suggestions: Suggestion[]): void {
    source.value = src
    analysisId.value = analysis
    const mine = items.value.filter((i) => !i.ai_suggested)
    const ai = suggestions.map<DraftItem>((s) => ({
      key: nextKey++, food_id: s.food_id, name_el: s.name_el, food_group: null, portion: s.portion ?? null,
      ai_suggested: true, confidence_word: s.confidence_word, alternatives: s.alternatives ?? [], removed: false,
    }))
    items.value = [...ai, ...mine].slice(0, MAX_ITEMS_PER_MEAL)
  }

  function addFood(food: Food): boolean {
    if (isFull.value) return false
    if (active.value.some((i) => i.food_id === food.food_id)) return true
    items.value.push({ key: nextKey++, food_id: food.food_id, name_el: food.name_el, food_group: food.food_group, portion: null,
      ai_suggested: false, confidence_word: null, alternatives: [], removed: false })
    return true
  }
  function hasFood(foodId: string): boolean { return active.value.some((i) => i.food_id === foodId) }

  function setPortion(key: number, portion: Portion): void {
    const it = items.value.find((i) => i.key === key)
    if (it) it.portion = portion
  }
  function remove(key: number): void {
    const it = items.value.find((i) => i.key === key)
    if (it) it.removed = true
  }
  function restore(key: number): void {
    const it = items.value.find((i) => i.key === key)
    if (it && !isFull.value) it.removed = false
  }
  /** S08β: το παιδί διάλεξε εναλλακτική για γραμμή χωρίς αντιστοίχιση. */
  function chooseAlternative(key: number, alt: Alternative): void {
    const it = items.value.find((i) => i.key === key)
    if (it) { it.food_id = alt.food_id; it.name_el = alt.name_el }
  }

  function body(): ConfirmBody {
    const b: ConfirmBody = {
      client_meal_id: clientMealId.value, eaten_on: eatenOn.value, meal_slot: slot.value, source: source.value,
      items: active.value.map((i) => ({ food_id: i.food_id as string, portion: i.portion as Portion, ai_suggested: i.ai_suggested })),
    }
    if (analysisId.value) b.analysis_id = analysisId.value
    return b
  }

  return { slot, eatenOn, source, analysisId, clientMealId, items, text, image, active, unresolved, withoutPortion, canSave, isFull,
    start, setImage, applySuggestions, addFood, hasFood, setPortion, remove, restore, chooseAlternative, body }
})
