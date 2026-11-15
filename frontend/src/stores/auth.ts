/**
 * Συνεδρία: JWT σε localStorage (η PWA δεν πρέπει να ζητά το κλειδί σε κάθε άνοιγμα· ο server το ακυρώνει με
 * token_version). Το κλειδί πρόσβασης ΔΕΝ αποθηκεύεται ποτέ. Ακολουθεί και ένα σημάδι «έγινε onboarding».
 */
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import * as authApi from '@/api/auth'
import { useMealsStore } from '@/stores/meals'
import { useQueueStore } from '@/stores/queue'

const TOKEN_KEY = 'pyramid.token'
const EXPIRES_KEY = 'pyramid.token_expires_at'
const ONBOARDED_KEY = 'pyramid.onboarded'

function read(key: string): string | null {
  try { return localStorage.getItem(key) } catch { return null }
}
function write(key: string, value: string | null): void {
  try { value === null ? localStorage.removeItem(key) : localStorage.setItem(key, value) } catch { /* private mode */ }
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(read(TOKEN_KEY))
  const expiresAt = ref<number | null>(Number(read(EXPIRES_KEY)) || null)
  const onboarded = ref(read(ONBOARDED_KEY) === '1')
  const sessionExpired = ref(false)         // M09

  const isLoggedIn = computed(() => !!token.value && (expiresAt.value === null || expiresAt.value > Date.now()))

  async function login(accessKey: string): Promise<void> {
    const res = await authApi.login(accessKey.trim())
    token.value = res.access_token
    expiresAt.value = Date.now() + res.expires_in * 1000
    sessionExpired.value = false
    write(TOKEN_KEY, token.value)
    write(EXPIRES_KEY, String(expiresAt.value))
  }

  function logout(): void {
    token.value = null
    expiresAt.value = null
    write(TOKEN_KEY, null)
    write(EXPIRES_KEY, null)
    useMealsStore().clear()                 // τα αποθηκευμένα του S04δ φεύγουν μαζί με τη συνεδρία
    useQueueStore().clear()
  }

  /** 401 με token: η σύνδεση έληξε ή ανακλήθηκε → M09, μετά είσοδος. */
  function expire(): void {
    if (!token.value) return
    logout()
    sessionExpired.value = true
  }

  function markOnboarded(): void {
    onboarded.value = true
    write(ONBOARDED_KEY, '1')
  }

  return { token, isLoggedIn, onboarded, sessionExpired, login, logout, expire, markOnboarded }
})
