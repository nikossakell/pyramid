<script setup lang="ts">
// M09 SessionExpired: μετά από 401 με token. «Μπες ξανά» → S02.
import { useRouter } from 'vue-router'
import CenterDialog from '@/components/ui/CenterDialog.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'
import { useAuthStore } from '@/stores/auth'
import { useMeStore } from '@/stores/me'

const auth = useAuthStore()
const me = useMeStore()
const router = useRouter()
function again(): void {
  auth.sessionExpired = false
  me.clear()
  router.replace({ name: 'login' })
}
</script>

<template>
  <CenterDialog :open="auth.sessionExpired" labelled-by="m09-title">
    <span class="ico"><Icon name="lock" :size="26" /></span>
    <h2 id="m09-title" class="t-title">Μπες ξανά με το κλειδί σου</h2>
    <p class="t-body">Η σύνδεσή σου έληξε.</p>
    <AppButton @click="again">Μπες ξανά</AppButton>
  </CenterDialog>
</template>

<style scoped>
.ico { width: 56px; height: 56px; border-radius: 18px; background: var(--color-surface); display: flex; align-items: center; justify-content: center; }
</style>
