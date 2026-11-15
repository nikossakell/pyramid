/**
 * Ουρά εκτός σύνδεσης (S04δ / S20α, mockups_delta §7): ΜΟΝΟ επιβεβαιώσεις που χτίστηκαν από την αναζήτηση (source=manual),
 * γιατί κείμενο και φωτογραφία χρειάζονται τον server ούτως ή άλλως. Σε localStorage μένουν μόνο το σώμα του
 * /meals/confirm (κωδικοί τροφίμων, μερίδες ως λέξεις) και τα ονόματα για την ένδειξη «σε αναμονή αποστολής».
 * Ποτέ εικόνα, ποτέ κείμενο του παιδιού. Επανάληψη με το ίδιο client_meal_id (idempotent). 422 / 409 → αφαιρείται με το
 * ήπιο μήνυμα «Αυτή η καταγραφή δεν στάλθηκε. Γράψ' τη ξανά.»
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { ApiError, OFFLINE } from '@/api/client'
import { confirmMeal, type ConfirmBody, type MealSlot } from '@/api/meals'

const KEY = 'pyramid.queue.v1'
export type QueuedConfirm = { body: ConfirmBody; names: string[]; groups: string[]; queuedAt: number }

function read(): QueuedConfirm[] {
  try { return JSON.parse(localStorage.getItem(KEY) ?? '[]') } catch { return [] }
}
function write(q: QueuedConfirm[]): void {
  try { q.length ? localStorage.setItem(KEY, JSON.stringify(q)) : localStorage.removeItem(KEY) } catch { /* ignore */ }
}

export const useQueueStore = defineStore('queue', () => {
  const entries = ref<QueuedConfirm[]>(read())
  const flushing = ref(false)
  const rejectedCount = ref(0)                     // για το toast μετά την επανασύνδεση
  const sentCount = ref(0)

  const pending = computed(() => entries.value.map((e) => ({ slot: e.body.meal_slot as MealSlot, names: e.names, day: e.body.eaten_on })))

  function enqueue(entry: Omit<QueuedConfirm, 'queuedAt'>): void {
    entries.value = [...entries.value, { ...entry, queuedAt: Date.now() }]
    write(entries.value)
  }

  /** Στέλνει ό,τι περιμένει. Επιστρέφει {sent, rejected}. Σταματά στο πρώτο σφάλμα δικτύου. */
  async function flush(): Promise<{ sent: number; rejected: number }> {
    if (flushing.value || !navigator.onLine) return { sent: 0, rejected: 0 }
    flushing.value = true
    let sent = 0, rejected = 0
    try {
      for (const e of [...entries.value]) {
        try {
          await confirmMeal(e.body)
          sent++
        } catch (err) {
          if (err instanceof ApiError && (err.status === 422 || err.status === 409)) rejected++
          else break                                                   // offline, 5xx, 401/403: μένει
        }
        entries.value = entries.value.filter((x) => x !== e)
        write(entries.value)
      }
    } finally {
      flushing.value = false
    }
    sentCount.value += sent
    rejectedCount.value += rejected
    return { sent, rejected }
  }

  function clear(): void {
    entries.value = []
    write([])
  }

  return { entries, pending, flushing, rejectedCount, sentCount, enqueue, flush, clear }
})
