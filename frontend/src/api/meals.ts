// Γεύματα και ημέρες. Καμία απάντηση δεν έχει γραμμάρια ή θρεπτικά (R1). Η φωτογραφία πάει ως raw image/jpeg (Blob στη
// μνήμη, ποτέ σε storage). Τίποτα δεν αποθηκεύεται στον server χωρίς /meals/confirm (R5).
import { api, request } from './client'

export type MealSlot = 'breakfast' | 'morning_snack' | 'lunch' | 'afternoon_snack' | 'dinner' | 'snack'
export type MealSource = 'camera' | 'text' | 'manual'
export type Portion = 'small' | 'medium' | 'large'

export type MealItem = { food_id: string; name_el: string; portion: Portion; food_group: string | null; ai_suggested: boolean }
export type Meal = { meal_id: string; eaten_on: string; meal_slot: MealSlot; source: MealSource; created_at: string; items: MealItem[] }
export type Day = { day: string; completed: boolean }

export type Alternative = { food_id: string; name_el: string }
export type Suggestion = {
  food_id: string | null                 // null: δεν βρέθηκε στον πίνακα → το παιδί διαλέγει από alternatives ή ψάχνει
  name_el: string
  confidence_word: 'σίγουρο' | 'ίσως'    // ποτέ αριθμός (R1)
  alternatives: Alternative[]            // 0–3
  portion: Portion | null                // πάντα null σήμερα
  components: null
}
export type Suggestions = { analysis_id: string; suggestions: Suggestion[]; needs_confirmation: true }

export type ConfirmItem = { food_id: string; portion: Portion; ai_suggested: boolean }
export type ConfirmBody = { client_meal_id: string; eaten_on: string; meal_slot: MealSlot; source: MealSource; items: ConfirmItem[]; analysis_id?: string }
export type ConfirmOut = { meal_id: string; eaten_on: string; meal_slot: MealSlot; food_groups: string[]; created: boolean }

export const MAX_ITEMS_PER_MEAL = 10
export const TEXT_MAX_LENGTH = 300

/** Σειρά και ετικέτες των θέσεων γεύματος (C11). */
export const MEAL_SLOTS: { slot: MealSlot; label: string }[] = [
  { slot: 'breakfast', label: 'Πρωινό' },
  { slot: 'morning_snack', label: 'Δεκατιανό' },
  { slot: 'lunch', label: 'Μεσημεριανό' },
  { slot: 'afternoon_snack', label: 'Απογευματινό' },
  { slot: 'dinner', label: 'Βραδινό' },
  { slot: 'snack', label: 'Σνακ' },
]
export const slotLabel = (slot: MealSlot): string => MEAL_SLOTS.find((s) => s.slot === slot)?.label ?? slot
export const PORTIONS: { value: Portion; label: string }[] = [
  { value: 'small', label: 'Μικρή' }, { value: 'medium', label: 'Μεσαία' }, { value: 'large', label: 'Μεγάλη' },
]

export const listMeals = (from: string, to: string) => api.get<Meal[]>('/meals', { from, to })
export const listDays = (from: string, to: string) => api.get<Day[]>('/days', { from, to })
export const completeDay = (day: string) => api.post<Day>(`/days/${day}/complete`)

export const analyzePhoto = (blob: Blob, signal?: AbortSignal, timeoutMs = 25_000) =>
  request<Suggestions>('/meals/photo', { method: 'POST', blob, signal, timeoutMs })
export const analyzeText = (text: string, timeoutMs = 25_000) =>
  request<Suggestions>('/meals/text', { method: 'POST', json: { text }, timeoutMs })
export const confirmMeal = (body: ConfirmBody) => api.post<ConfirmOut>('/meals/confirm', body)
export const deleteMeal = (mealId: string) => api.delete<void>(`/meals/${mealId}`)
