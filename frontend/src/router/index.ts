/**
 * Διαδρομές και φύλακες. Χωρίς token → S02. Με token και χωρίς onboarding → S03.
 * Οι καταστάσεις 401 / 403 των αιτημάτων οδηγούν σε M09 / S19 / S21 (installApiHandlers, εδώ).
 */
import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { installApiHandlers } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useMeStore } from '@/stores/me'

declare module 'vue-router' {
  interface RouteMeta {
    public?: boolean          // χωρίς token
    title?: string
    offlineText?: string      // κείμενο της C28 OfflineBanner για τη συγκεκριμένη οθόνη (S01δ, S02δ)
  }
}

const routes: RouteRecordRaw[] = [
  { path: '/', name: 'splash', component: () => import('@/views/SplashView.vue'), meta: { public: true, offlineText: 'Είσαι εκτός σύνδεσης.' } },
  { path: '/login', name: 'login', component: () => import('@/views/LoginView.vue'), meta: { public: true, offlineText: 'Είσαι εκτός σύνδεσης. Η είσοδος χρειάζεται ίντερνετ.' } },
  { path: '/onboarding', name: 'onboarding', component: () => import('@/views/OnboardingView.vue') },
  { path: '/today', name: 'today', component: () => import('@/views/TodayView.vue') },
  { path: '/log', name: 'log', component: () => import('@/views/TodayView.vue'), props: { openLog: true } },
  { path: '/log/camera', name: 'camera', component: () => import('@/views/CameraView.vue') },
  { path: '/log/analysis', name: 'analysis', component: () => import('@/views/AnalysisView.vue') },
  { path: '/log/confirm', name: 'confirm', component: () => import('@/views/ConfirmView.vue') },
  { path: '/log/text', name: 'text', component: () => import('@/views/TextLogView.vue') },
  { path: '/log/search', name: 'search', component: () => import('@/views/SearchView.vue') },
  { path: '/log/saved', name: 'saved', component: () => import('@/views/SavedView.vue') },
  { path: '/history', name: 'history', component: () => import('@/views/HistoryView.vue') },
  { path: '/history/meal/:id', name: 'meal', component: () => import('@/views/MealDetailView.vue') },
  { path: '/chat', name: 'chat', component: () => import('@/views/PlaceholderView.vue'), props: { tab: 'chat' } },
  { path: '/cards', name: 'cards', component: () => import('@/views/PlaceholderView.vue'), props: { tab: 'cards' } },
  { path: '/profile', name: 'profile', component: () => import('@/views/ProfileView.vue') },
  { path: '/privacy', name: 'privacy', component: () => import('@/views/PrivacyView.vue') },
  { path: '/study-ended', name: 'study-ended', component: () => import('@/views/StudyEndView.vue'), meta: { public: true } },
  { path: '/not-yet', name: 'not-yet', component: () => import('@/views/NotYetOpenView.vue'), meta: { public: true } },
  { path: '/error', name: 'error', component: () => import('@/views/ErrorView.vue'), meta: { public: true } },
  { path: '/:pathMatch(.*)*', redirect: '/' },
]

export const router = createRouter({
  history: createWebHistory(),
  routes,
  scrollBehavior: () => ({ top: 0 }),
})

router.beforeEach((to) => {
  const auth = useAuthStore()
  if (to.name === 'login' && auth.isLoggedIn) return { name: auth.onboarded ? 'today' : 'onboarding' }
  if (to.meta.public) return true
  if (!auth.isLoggedIn) return { name: 'login' }
  if (!auth.onboarded && to.name !== 'onboarding') return { name: 'onboarding' }
  return true
})

// S20β: αποτυχία φόρτωσης chunk ή απρόβλεπτο σφάλμα πλοήγησης → γενικό σφάλμα («Δεν φταις εσύ»).
router.onError(() => { router.replace({ name: 'error' }).catch(() => {}) })

installApiHandlers({
  token: () => useAuthStore().token,
  onUnauthorized: () => useAuthStore().expire(),                 // M09
  onStudyEnded: () => {
    useAuthStore().logout()
    useMeStore().clear()
    router.replace({ name: 'study-ended' })                        // S19, σε οποιοδήποτε αίτημα
  },
  onNotYetAvailable: () => router.replace({ name: 'not-yet' }),  // S21
})
