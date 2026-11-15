<script setup lang="ts">
// Ρίζα: εφαρμόζει θέμα / μέγεθος κειμένου / κίνηση, δείχνει OfflineBanner, Toast, HelpSheet (M01) και M09.
// Στέλνει την ουρά εκτός σύνδεσης (μόνο καταγραφές από αναζήτηση) στην εκκίνηση και σε κάθε επανασύνδεση (S20α).
import { onMounted, watch } from 'vue'
import { RouterView, useRoute } from 'vue-router'
import { useUiStore } from '@/stores/ui'
import { useAuthStore } from '@/stores/auth'
import { useQueueStore } from '@/stores/queue'
import OfflineBanner from '@/components/ui/OfflineBanner.vue'
import ToastHost from '@/components/ui/ToastHost.vue'
import HelpSheet from '@/components/modals/HelpSheet.vue'
import SessionExpired from '@/components/modals/SessionExpired.vue'

const ui = useUiStore()
const auth = useAuthStore()
const queue = useQueueStore()
const route = useRoute()

async function flushQueue(): Promise<void> {
  if (!auth.isLoggedIn || !queue.entries.length) return
  const { rejected } = await queue.flush()
  for (let i = 0; i < rejected; i++) ui.toast('Αυτή η καταγραφή δεν στάλθηκε. Γράψ’ τη ξανά.', 'info')
}

onMounted(() => { ui.applyPreferences(); flushQueue() })
watch(() => ui.online, (on) => { if (on) flushQueue() })
</script>

<template>
  <OfflineBanner :text="route.meta.offlineText" />
  <RouterView />
  <ToastHost />
  <HelpSheet />
  <SessionExpired />
</template>
