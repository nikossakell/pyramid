<script setup lang="ts">
// Ρίζα: εφαρμόζει θέμα / μέγεθος κειμένου / κίνηση, δείχνει OfflineBanner, Toast, HelpSheet (M01) και M09.
// Στέλνει την ουρά εκτός σύνδεσης (μόνο καταγραφές από αναζήτηση) στην εκκίνηση και σε κάθε επανασύνδεση (S20α).
// Κέλυφος: σε expanded (≥ 1024) SideNav αριστερά σε κάθε οθόνη με token εκτός από την κάμερα και τις δημόσιες
// (S01, S02, S19, S20β, S21)· το OfflineBanner μένει πάνω από το περιεχόμενο, όχι πάνω από το SideNav.
import { computed, onMounted, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { useQueueStore } from '@/stores/queue'
import { useBreakpoint } from '@/composables/useBreakpoint'
import OfflineBanner from '@/components/ui/OfflineBanner.vue'
import ToastHost from '@/components/ui/ToastHost.vue'
import SideNav, { type NavKey } from '@/components/ui/SideNav.vue'
import HelpSheet from '@/components/modals/HelpSheet.vue'
import SessionExpired from '@/components/modals/SessionExpired.vue'

const ui = useUiStore()
const auth = useAuthStore()
const queue = useQueueStore()
const route = useRoute()
const { isExpanded } = useBreakpoint()

const NAV_BY_ROUTE: Record<string, NavKey> = {
  today: 'today', log: 'today', history: 'history', meal: 'history', chat: 'chat', cards: 'cards',
  profile: 'profile', privacy: 'profile', analysis: 'log', confirm: 'log', text: 'log', search: 'log', saved: 'log',
}
const showNav = computed(() => isExpanded.value && auth.isLoggedIn && !route.meta.public && route.name !== 'camera')
const navActive = computed<NavKey>(() => NAV_BY_ROUTE[String(route.name ?? '')] ?? 'none')

async function flushQueue(): Promise<void> {
  if (!auth.isLoggedIn || !queue.entries.length) return
  const { rejected } = await queue.flush()
  for (let i = 0; i < rejected; i++) ui.toast('Αυτή η καταγραφή δεν στάλθηκε. Γράψ’ τη ξανά.', 'info')
}

onMounted(() => { ui.applyPreferences(); flushQueue() })
watch(() => ui.online, (on) => { if (on) flushQueue() })
</script>

<template>
  <div class="app" :class="{ 'app--nav': showNav }">
    <SideNav v-if="showNav" :active="navActive" />
    <div class="app__page">
      <OfflineBanner :text="route.meta.offlineText" />
      <RouterView />
    </div>
  </div>
  <ToastHost />
  <HelpSheet />
  <SessionExpired />
</template>
