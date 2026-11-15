/** Ημερομηνίες σε τοπική ζώνη της συσκευής, μορφή YYYY-MM-DD (ίδια με το backend, που δουλεύει με ώρα Ελλάδας). */

export function toIsoDate(d: Date): string {
  const y = d.getFullYear(), m = String(d.getMonth() + 1).padStart(2, '0'), day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}
export const todayIso = (): string => toIsoDate(new Date())

export function addDays(iso: string, n: number): string {
  const [y, m, d] = iso.split('-').map(Number)
  return toIsoDate(new Date(y, m - 1, d + n))
}

/** Δευτέρα της εβδομάδας που περιέχει την ημερομηνία. */
export function weekStart(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  const dt = new Date(y, m - 1, d)
  const offset = (dt.getDay() + 6) % 7      // Δευτέρα = 0
  return addDays(iso, -offset)
}

export const WEEKDAY_LETTERS = ['Δ', 'Τ', 'Τ', 'Π', 'Π', 'Σ', 'Κ']
export const WEEKDAY_NAMES = ['Δευτέρα', 'Τρίτη', 'Τετάρτη', 'Πέμπτη', 'Παρασκευή', 'Σάββατο', 'Κυριακή']

/** «Καλημέρα!» μέχρι το μεσημέρι, μετά «Καλησπέρα!». */
export function greeting(now = new Date()): string {
  return now.getHours() < 12 ? 'Καλημέρα!' : 'Καλησπέρα!'
}

/** Όνομα ημέρας («Δευτέρα») μιας ημερομηνίας. */
export function weekdayName(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return WEEKDAY_NAMES[(new Date(y, m - 1, d).getDay() + 6) % 7]
}

/** Σύντομη ελληνική ημερομηνία για το S12 («Τρίτη 12 Νοεμβρίου»). */
export function longDate(iso: string): string {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleDateString('el-GR', { weekday: 'long', day: 'numeric', month: 'long' })
}
