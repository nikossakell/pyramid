/**
 * UI: προτιμήσεις (S17: μέγεθος κειμένου, θέμα, μείωση κίνησης) σε localStorage, online/offline, toasts (C27),
 * HelpSheet (M01). Τίποτα από αυτά δεν είναι δεδομένο της μελέτης.
 */
import { defineStore } from 'pinia'
import { ref } from 'vue'

export type TextSize = 'normal' | 'large' | 'xlarge'
export type Theme = 'light' | 'dark' | 'auto'
export type Toast = { id: number; text: string; kind: 'success' | 'info' | 'error'; action?: { label: string; run: () => void } }

const PREFS_KEY = 'pyramid.prefs'
type Prefs = { textSize: TextSize; theme: Theme; reduceMotion: boolean }
const DEFAULTS: Prefs = { textSize: 'normal', theme: 'auto', reduceMotion: false }

function loadPrefs(): Prefs {
  try { return { ...DEFAULTS, ...JSON.parse(localStorage.getItem(PREFS_KEY) ?? '{}') } } catch { return { ...DEFAULTS } }
}

export const useUiStore = defineStore('ui', () => {
  const prefs = ref<Prefs>(loadPrefs())
  const online = ref(navigator.onLine)
  const toasts = ref<Toast[]>([])
  const helpOpen = ref(false)
  const reconnected = ref(false)          // C28 «Συνδέθηκες ξανά.» κρύβεται αυτόματα
  let nextId = 1

  function applyPreferences(): void {
    const root = document.documentElement
    const dark = prefs.value.theme === 'dark' || (prefs.value.theme === 'auto' && window.matchMedia('(prefers-color-scheme: dark)').matches)
    root.dataset.theme = dark ? 'dark' : 'light'
    root.dataset.text = prefs.value.textSize
    root.dataset.motion = prefs.value.reduceMotion ? 'reduce' : 'full'
    document.querySelector('meta[name="theme-color"]')?.setAttribute('content', dark ? '#121110' : '#ffffff')
    try { localStorage.setItem(PREFS_KEY, JSON.stringify(prefs.value)) } catch { /* ignore */ }
  }

  function setPrefs(patch: Partial<Prefs>): void {
    prefs.value = { ...prefs.value, ...patch }
    applyPreferences()
  }

  function toast(text: string, kind: Toast['kind'] = 'info', action?: Toast['action']): void {
    const id = nextId++
    toasts.value.push({ id, text, kind, action })
    setTimeout(() => dismiss(id), kind === 'error' ? 8000 : 4000)
  }
  function dismiss(id: number): void {
    toasts.value = toasts.value.filter((t) => t.id !== id)
  }

  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', applyPreferences)
  window.addEventListener('offline', () => { online.value = false; reconnected.value = false })
  window.addEventListener('online', () => {
    online.value = true
    reconnected.value = true
    setTimeout(() => { reconnected.value = false }, 3000)
  })

  return { prefs, online, reconnected, toasts, helpOpen, applyPreferences, setPrefs, toast, dismiss }
})
