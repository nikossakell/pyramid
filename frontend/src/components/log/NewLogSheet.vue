<script setup lang="ts">
// S05 Νέα καταγραφή (ΚΡΑΤΑ): sheet πάνω από το S04. Θέση γεύματος (από την ώρα ή από την κενή θέση), τρεις δρόμοι:
// Φωτογραφία (ανενεργή όταν photo_status ≠ available, mockups_delta §2), Γράψε, Ψάξε. Το tag «Προπόνηση» είναι
// ΑΠΟΦΑΣΗ χωρίς πεδίο στο backend: δεν υλοποιείται. API: GET /me (photo_status) σε κάθε άνοιγμα.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import BottomSheet from '@/components/ui/BottomSheet.vue'
import Icon from '@/components/ui/Icon.vue'
import SlotChips from './SlotChips.vue'
import { slotLabel, type MealSlot } from '@/api/meals'
import { PHOTO_UNAVAILABLE_COPY } from '@/lib/copy'
import { useLogStore } from '@/stores/log'
import { useMeStore } from '@/stores/me'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const props = defineProps<{ open: boolean; slot?: MealSlot | null; fromSlot?: boolean }>()
const emit = defineEmits<{ close: []; camera: [] }>()
const router = useRouter()
const log = useLogStore()
const me = useMeStore()

// Χωρίς κάμερα στη συσκευή (π.χ. υπολογιστής χωρίς webcam, ή browser χωρίς getUserMedia) η «Φωτογραφία» είναι ανενεργή με το
// ίδιο ουδέτερο κείμενο (delta §2)· ποτέ επιλογή αρχείου ή γκαλερί (S06). Το enumerateDevices δεν ζητά άδεια.
const hasCamera = ref(true)
const photoOk = computed(() => me.photoStatus === 'available' && hasCamera.value)
const title = computed(() => (props.fromSlot ? slotLabel(log.slot) : 'Νέα καταγραφή'))

async function detectCamera(): Promise<void> {
  if (!navigator.mediaDevices?.getUserMedia) { hasCamera.value = false; return }
  try {
    const devices = await navigator.mediaDevices.enumerateDevices?.()
    if (Array.isArray(devices) && devices.length > 0) hasCamera.value = devices.some((d) => d.kind === 'videoinput')
  } catch { /* άγνωστο: αφήνουμε την κάμερα να δοκιμάσει (S06β καλύπτει την αποτυχία) */ }
}

onMounted(() => {
  // Πρόχειρο σε εξέλιξη (π.χ. «Πίσω» από το S08) δεν χάνεται· καθαρίζει μόνο με «Ακύρωση» ή μετά το S11.
  if (log.active.length === 0 && !log.text) log.start(props.slot ?? undefined)
  else if (props.slot) log.slot = props.slot
  me.load(true).catch(() => {})
  detectCamera()
})

const OPTIONS = [
  { key: 'camera', icon: 'camera', title: 'Φωτογραφία', sub: 'Μόνο το πιάτο, χωρίς πρόσωπα' },
  { key: 'text', icon: 'pencil', title: 'Γράψε τι έφαγες', sub: 'Με δικά σου λόγια' },
  { key: 'search', icon: 'search', title: 'Ψάξε φαγητό', sub: 'Από τη λίστα τροφίμων' },
] as const

/** S20α: εκτός σύνδεσης μόνο η αναζήτηση (από τα πρόσφατα, μπαίνει στην ουρά)· φωτογραφία και κείμενο θέλουν τον server. */
function isOff(key: 'camera' | 'text' | 'search'): boolean {
  if (!ui.online) return key !== 'search'
  return key === 'camera' && !photoOk.value
}
function go(key: 'camera' | 'text' | 'search'): void {
  if (isOff(key)) return
  if (key === 'camera') { emit('camera'); return }
  router.push({ name: key })
}
</script>

<template>
  <BottomSheet :open="open" labelled-by="newlog-title" close-button @close="emit('close')">
    <h2 id="newlog-title" class="t-title head">{{ title }}</h2>
    <fieldset class="fs">
      <legend class="legend">Γεύμα</legend>
      <SlotChips v-model="log.slot" />
    </fieldset>
    <div class="opts">
      <button v-for="o in OPTIONS" :key="o.key" type="button" class="opt pressable" :class="{ 'opt--off': isOff(o.key), 'opt--queue': !ui.online && o.key === 'search' }"
              :aria-disabled="isOff(o.key) ? 'true' : undefined" @click="go(o.key)">
        <span class="ico"><Icon :name="o.icon" :size="24" /></span>
        <span class="txt">
          <span class="t1">{{ o.title }}</span>
          <span v-if="!ui.online && o.key !== 'search'" class="t2 muted">Χρειάζεται σύνδεση</span>
          <span v-else-if="!ui.online" class="t2 muted">Από τα πρόσφατα · θα σταλεί μόλις συνδεθείς</span>
          <span v-else-if="o.key === 'camera' && !photoOk" class="t2">{{ PHOTO_UNAVAILABLE_COPY }} <span class="muted">[*προς έγκριση]</span></span>
          <span v-else class="t2 muted">{{ o.sub }}</span>
        </span>
      </button>
    </div>
  </BottomSheet>
</template>

<style scoped>
.head { margin-top: -44px; padding-right: 56px; }
.fs { border: 0; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.legend { font-weight: 700; font-size: calc(14px * var(--text-scale)); padding: 0 0 8px; }
.opts { display: flex; flex-direction: column; gap: 10px; }
.opt { display: flex; align-items: center; gap: 14px; border: 1.5px solid var(--color-line); border-radius: 18px; padding: 10px 14px; background: var(--color-bg); text-align: left; color: inherit; min-height: 68px; }
.opt--off { color: var(--color-text-muted); cursor: default; }
.opt--off .ico { opacity: 0.6; }
.opt--off { background: var(--color-surface); }
.opt--queue { border: 2px solid var(--color-ink); }
.ico { width: 48px; height: 48px; border-radius: 14px; background: var(--color-surface); display: flex; align-items: center; justify-content: center; flex: none; }
.txt { display: flex; flex-direction: column; gap: 2px; }
.t1 { font-weight: 600; font-size: calc(17px * var(--text-scale)); }
.t2 { font-size: calc(13px * var(--text-scale)); line-height: 1.35; }
/* expanded: dialog με τις τρεις επιλογές ως τρεις κάρτες σε μία σειρά, η επιλογή γεύματος από πάνω */
@media (min-width: 1024px) {
  .head { margin-top: -52px; }
  .opts { flex-direction: row; align-items: stretch; }
  .opt { flex: 1 1 0; min-width: 0; flex-direction: column; align-items: flex-start; gap: 12px; padding: 16px 14px 14px; min-height: 150px; }
  .ico { width: 52px; height: 52px; }
  .txt { gap: 4px; }
  @media (hover: hover) { .opt:not(.opt--off):hover { background: var(--color-surface); filter: none; } }
}
</style>
