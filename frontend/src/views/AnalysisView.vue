<script setup lang="ts">
// S07 Ανάλυση σε εξέλιξη (ΚΡΑΤΑ) + C08 AnalysisLoader. POST /meals/photo (raw image/jpeg από τη μνήμη).
// επιτυχία → S08 · 422 rejected → M05 (ίδιο κείμενο για κάθε αιτία) · χαμηλή βεβαιότητα → M06 · λήξη/σφάλμα → «Άργησε πολύ»
// · 403/503 photo_unavailable → ίδιο ουδέτερο κείμενο με το S05 (mockups_delta §2). Η εικόνα ξεχνιέται μετά την απάντηση.
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import AppButton from '@/components/ui/AppButton.vue'
import NotFoodDetected from '@/components/modals/NotFoodDetected.vue'
import LowConfidence from '@/components/modals/LowConfidence.vue'
import { ApiError } from '@/api/client'
import { analyzePhoto, type Alternative, type Suggestions } from '@/api/meals'
import { PHOTO_UNAVAILABLE_COPY } from '@/lib/copy'
import { useLogStore } from '@/stores/log'
import { useMeStore } from '@/stores/me'

const router = useRouter()
const log = useLogStore()
const me = useMeStore()

type State = 'running' | 'slow' | 'timeout' | 'unavailable' | 'rejected' | 'lowconf'
const state = ref<State>('running')
const lowOptions = ref<Alternative[]>([])
let result: Suggestions | null = null
let controller: AbortController | null = null
let slowTimer: ReturnType<typeof setTimeout> | null = null

const headline = computed(() => (state.value === 'slow' ? 'Λίγο ακόμα…' : 'Βλέπω τι έχει το πιάτο…'))

function toText(): void { log.setImage(null); router.replace({ name: 'text' }) }
function toSearch(): void { log.setImage(null); router.replace({ name: 'search' }) }
function retry(): void { log.setImage(null); router.replace({ name: 'camera' }) }

async function run(): Promise<void> {
  const blob = log.image
  if (!blob) { router.replace({ name: 'log' }); return }
  state.value = 'running'
  controller = new AbortController()
  slowTimer = setTimeout(() => { if (state.value === 'running') state.value = 'slow' }, 8000)
  try {
    const res = await analyzePhoto(blob, controller.signal)
    log.setImage(null)
    result = res
    const s = res.suggestions
    if (s.length === 0) { state.value = 'rejected'; return }
    // Χαμηλή βεβαιότητα: μία πρόταση «ίσως» με εναλλακτικές → M06
    if (s.length === 1 && s[0].confidence_word === 'ίσως' && s[0].alternatives.length > 0) {
      lowOptions.value = [...(s[0].food_id ? [{ food_id: s[0].food_id, name_el: s[0].name_el }] : []), ...s[0].alternatives].slice(0, 3)
      state.value = 'lowconf'
      return
    }
    log.applySuggestions('camera', res.analysis_id, s)
    router.replace({ name: 'confirm' })
  } catch (e) {
    log.setImage(null)
    if (e instanceof ApiError && e.status === 422) state.value = 'rejected'
    else if (e instanceof ApiError && (e.status === 403 || e.status === 503) && e.detail === 'photo_unavailable') {
      state.value = 'unavailable'
      me.load(true).catch(() => {})
    } else if (e instanceof ApiError && (e.status === 401 || e.status === 403)) { /* πλοήγηση από τον client */ }
    else state.value = 'timeout'
  } finally {
    if (slowTimer) clearTimeout(slowTimer)
  }
}

function pickLow(a: Alternative): void {
  if (!result) return
  const s = result.suggestions[0]
  log.applySuggestions('camera', result.analysis_id, [{ ...s, food_id: a.food_id, name_el: a.name_el, alternatives: [] }])
  router.replace({ name: 'confirm' })
}

function cancel(): void {
  controller?.abort()
  toText()
}

onMounted(run)
onBeforeUnmount(() => { controller?.abort(); if (slowTimer) clearTimeout(slowTimer); log.setImage(null) })
</script>

<template>
  <div class="screen">
    <TopBar back :avatar="false" back-to="/log" />
    <main class="screen__body body">
      <template v-if="state === 'running' || state === 'slow'">
        <span class="blob" aria-hidden="true" />
        <h2 class="t-title">{{ headline }}</h2>
        <div class="bar" role="progressbar" aria-label="Ανάλυση φωτογραφίας"><span class="bar__in" /></div>
        <p class="t-label muted center">Η μικρογραφία υπάρχει μόνο στη μνήμη και δεν αποθηκεύεται.</p>
      </template>
      <template v-else-if="state === 'timeout'">
        <span class="blob blob--still" aria-hidden="true" />
        <p class="t-body center">Άργησε πολύ. Γράψε τι έφαγες ή δοκίμασε ξανά.</p>
      </template>
      <template v-else-if="state === 'unavailable'">
        <span class="blob blob--still" aria-hidden="true" />
        <p class="t-body center">{{ PHOTO_UNAVAILABLE_COPY }} <span class="muted">[*προς έγκριση]</span></p>
      </template>
      <span v-else class="blob blob--still" aria-hidden="true" />
    </main>

    <footer v-if="state === 'slow'" class="screen__footer">
      <AppButton variant="secondary" @click="cancel">Ακύρωση και γράψ' το</AppButton>
    </footer>
    <footer v-else-if="state === 'timeout'" class="screen__footer">
      <AppButton @click="toText">Γράψε τι έφαγες</AppButton>
      <AppButton variant="secondary" @click="retry">Δοκίμασε ξανά</AppButton>
    </footer>
    <footer v-else-if="state === 'unavailable'" class="screen__footer">
      <AppButton @click="toText">Γράψε τι έφαγες</AppButton>
      <AppButton variant="secondary" @click="toSearch">Ψάξε φαγητό</AppButton>
    </footer>

    <NotFoodDetected :open="state === 'rejected'" @retry="retry" @text="toText" />
    <LowConfidence :open="state === 'lowconf'" :options="lowOptions" @pick="pickLow" @none="toSearch" />
  </div>
</template>

<style scoped>
.body { align-items: center; justify-content: center; gap: 28px; padding: 24px; }
.center { text-align: center; }
.blob { width: 200px; height: 200px; border-radius: 999px; background: var(--color-analysis-blob); animation: pulse 1.6s ease-in-out infinite; }
.blob--still { animation: none; width: 160px; height: 160px; }
@keyframes pulse { 0%, 100% { transform: scale(1); } 50% { transform: scale(1.06); } }
:root[data-motion='reduce'] .blob { animation: none; }
.bar { width: 200px; height: 8px; border-radius: 999px; background: var(--color-line); overflow: hidden; }
.bar__in { display: block; width: 40%; height: 100%; border-radius: 999px; background: var(--color-primary); animation: slide 1.4s ease-in-out infinite; }
@keyframes slide { 0% { transform: translateX(-100%); } 100% { transform: translateX(350%); } }
:root[data-motion='reduce'] .bar__in { animation-duration: 3s; }
</style>
