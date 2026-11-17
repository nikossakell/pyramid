<script setup lang="ts">
// S02 Είσοδος με κλειδί (ΚΡΑΤΑ). α κενό · β λάθος κλειδί (401, ίδιο μήνυμα για κάθε αποτυχία) · γ κλείδωμα (429 + Retry-After,
// «σε N λεπτά», χωρίς αντίστροφη μέτρηση) · δ εκτός σύνδεσης (κουμπί ανενεργό) · ε «Δεν έχω κλειδί» (sheet, χωρίς εγγραφή).
// 403 not_yet_available → S21 και 403 study_ended → S19 τα κάνει ο API client. Το κλειδί δεν αποθηκεύεται πουθενά.
import { computed, onBeforeUnmount, ref } from 'vue'
import { useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import PyramidMark from '@/components/ui/PyramidMark.vue'
import AccessKeyInput from '@/components/ui/AccessKeyInput.vue'
import AppButton from '@/components/ui/AppButton.vue'
import BottomSheet from '@/components/ui/BottomSheet.vue'
import Icon from '@/components/ui/Icon.vue'
import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useMeStore } from '@/stores/me'
import { useUiStore } from '@/stores/ui'

const router = useRouter()
const auth = useAuthStore()
const me = useMeStore()
const ui = useUiStore()

const key = ref('')
const error = ref<string | null>(null)
const lockedText = ref<string | null>(null)
const busy = ref(false)
const noKeyOpen = ref(false)
let unlockTimer: ReturnType<typeof setTimeout> | null = null

const locked = computed(() => lockedText.value !== null)
const canSubmit = computed(() => ui.online && !locked.value && key.value.trim().length > 0 && !busy.value)

function minutesText(seconds: number | null): string {
  const mins = Math.max(1, Math.ceil((seconds ?? 600) / 60))
  return mins === 1 ? 'σε ένα λεπτό' : `σε ${mins} λεπτά`
}

async function submit(): Promise<void> {
  if (!canSubmit.value) return
  busy.value = true
  error.value = null
  try {
    await auth.login(key.value)
    key.value = ''
    try {
      const m = await me.load(true)
      if (m?.avatar_id) auth.markOnboarded()
    } catch { /* συνεχίζουμε· το S04 θα ξαναπροσπαθήσει */ }
    router.replace({ name: auth.onboarded ? 'today' : 'onboarding' })
  } catch (e) {
    if (e instanceof ApiError && e.status === 401) {
      error.value = 'Αυτό το κλειδί δεν το αναγνωρίζουμε. Έλεγξε τα γράμματα και τους αριθμούς.'
    } else if (e instanceof ApiError && e.status === 429) {
      lockedText.value = `Έγιναν πολλές προσπάθειες. Δοκίμασε ξανά ${minutesText(e.retryAfter)}. Αν δεν θυμάσαι το κλειδί, ρώτα τον γονιό σου ή την ομάδα.`
      key.value = ''
      unlockTimer = setTimeout(() => { lockedText.value = null }, (e.retryAfter ?? 600) * 1000)
    } else if (e instanceof ApiError && e.status === 403) {
      /* S19 / S21: πλοήγηση από τον client */
    } else {
      ui.toast('Κάτι πήγε στραβά. Δοκίμασε ξανά σε λίγο.', 'error')
    }
  } finally {
    busy.value = false
  }
}

onBeforeUnmount(() => { if (unlockTimer) clearTimeout(unlockTimer) })
</script>

<template>
  <div class="screen">
    <TopBar :avatar="false" />
    <main class="screen__body body">
      <div class="hero">
        <PyramidMark :height="44" wordmark :word-size="40" />
        <p class="hero__line t-body muted">Κατέγραψε τι τρως, μάθε για το φαγητό, κέρδισε κάρτες.</p>
      </div>
      <div class="formcard">
        <h2 class="t-display">Μπες με το κλειδί σου</h2>
        <p class="t-body muted">Το κλειδί σού το έδωσε η ερευνητική ομάδα.</p>
        <form class="form" @submit.prevent="submit">
          <AccessKeyInput v-model="key" :error="error" :locked="locked" :locked-text="lockedText ?? undefined" @update:model-value="error = null" />
          <div class="stack">
            <AppButton type="submit" :disabled="!canSubmit" :loading="busy">Μπες</AppButton>
            <AppButton variant="ghost" @click="noKeyOpen = true">Δεν έχω κλειδί</AppButton>
          </div>
        </form>
      </div>
    </main>

    <BottomSheet :open="noKeyOpen" labelled-by="nokey-title" @close="noKeyOpen = false">
      <span class="sheet-ico"><Icon name="lock" :size="26" /></span>
      <h3 id="nokey-title" class="t-title">Δεν έχεις κλειδί;</h3>
      <p class="t-body">Το κλειδί το δίνει η ερευνητική ομάδα. Ρώτα τον γονιό σου ή την ομάδα.</p>
      <AppButton @click="noKeyOpen = false">Κατάλαβα</AppButton>
    </BottomSheet>
  </div>
</template>

<style scoped>
.body { padding: 28px 20px 40px; gap: 18px; }
/* compact/medium: ίδια ροή με πριν (οι wrappers δεν αλλάζουν τη διάταξη)· η φράση του hero είναι μόνο για το desktop */
.hero, .formcard { display: contents; }
.hero__line { display: none; }
.form { display: flex; flex-direction: column; gap: 18px; margin-top: 4px; }
/* expanded: δύο μισά, αριστερά πάνελ ταυτότητας, δεξιά κάρτα φόρμας 420 px */
@media (min-width: 1024px) {
  .body { display: grid; grid-template-columns: 1fr 1fr; align-items: center; gap: 48px; padding: 32px 32px 56px; min-height: calc(100dvh - var(--header-height)); }
  .hero { display: flex; flex-direction: column; justify-content: center; gap: 20px; background: var(--color-surface); border-radius: 28px; padding: 48px 40px; min-height: 420px; }
  .hero__line { display: block; font-size: calc(18px * var(--text-scale)); max-width: 28ch; }
  .formcard { display: flex; flex-direction: column; gap: 18px; width: 100%; max-width: 420px; justify-self: center; border: 1px solid var(--color-line); border-radius: 24px; padding: 32px 28px; box-shadow: var(--shadow-card); }
}
.sheet-ico { width: 56px; height: 56px; border-radius: 18px; background: var(--color-surface); display: flex; align-items: center; justify-content: center; }
</style>
