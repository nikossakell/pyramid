<script setup lang="ts">
// S01 Splash (ΚΡΑΤΑ). α: φόρτωση → S02 ή S04. δ: εκτός σύνδεσης → «Συνέχεια» (ό,τι είναι αποθηκευμένο) / «Δοκίμασε ξανά».
// Η κατάσταση β (λήψη φίλτρου φαγητού στη συσκευή) ανήκει στο food gate του browser: εκτός φάσης.
import { onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import PyramidMark from '@/components/ui/PyramidMark.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { useAuthStore } from '@/stores/auth'
import { useMeStore } from '@/stores/me'
import { useUiStore } from '@/stores/ui'

const router = useRouter()
const auth = useAuthStore()
const me = useMeStore()
const ui = useUiStore()
const offline = ref(false)

function next(): void {
  if (!auth.isLoggedIn) { router.replace({ name: 'login' }); return }
  router.replace({ name: auth.onboarded ? 'today' : 'onboarding' })
}

async function start(): Promise<void> {
  if (!ui.online) { offline.value = true; return }
  offline.value = false
  if (auth.isLoggedIn) {
    try {
      const m = await me.load(true)
      if (m?.avatar_id) auth.markOnboarded()      // άλλη συσκευή / νέα εγκατάσταση: το onboarding έχει γίνει
    } catch { /* 401/403 τα χειρίζεται ο client· αλλιώς συνεχίζουμε με ό,τι υπάρχει */ }
  }
  next()
}

onMounted(start)
</script>

<template>
  <div class="screen">
    <TopBar :avatar="false" />
    <main class="screen__body body">
      <div class="logo">
        <PyramidMark :height="112" />
        <span class="word">pyramid</span>
      </div>
      <span v-if="!offline" class="spinner" role="status" aria-label="Φόρτωση" />
    </main>
    <footer v-if="offline" class="screen__footer">
      <p class="t-body hint">Αν έχεις ξαναμπεί, θα δεις ό,τι είναι αποθηκευμένο στο κινητό. Για πρώτη είσοδο χρειάζεται σύνδεση.</p>
      <AppButton @click="next">Συνέχεια</AppButton>
      <AppButton variant="secondary" @click="start">Δοκίμασε ξανά</AppButton>
    </footer>
  </div>
</template>

<style scoped>
.body { align-items: center; justify-content: center; gap: 28px; }
.logo { display: flex; flex-direction: column; align-items: center; gap: 18px; }
.word { font-family: var(--font-display); font-size: 56px; line-height: 1; letter-spacing: -0.5px; }
.spinner { width: 28px; height: 28px; border-radius: 999px; border: 3px solid var(--color-line); border-top-color: var(--color-primary); animation: spin 0.9s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
:root[data-motion='reduce'] .spinner { animation-duration: 2s; }
.hint { padding: 0 8px 8px; }
</style>
