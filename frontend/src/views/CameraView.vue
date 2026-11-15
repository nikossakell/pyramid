<script setup lang="ts">
// S06 Κάμερα (ΚΡΑΤΑ): ζωντανή προεπισκόπηση με getUserMedia, χωρίς γκαλερί, χωρίς αποθήκευση εικόνας. Λήψη → canvas
// (≤ 448 px, JPEG, χωρίς EXIF) → Blob στη μνήμη → S07. β: άδεια αρνήθηκε → «Γράψε» / «Ψάξε». γ: ήπια υπόδειξη για σκοτάδι.
// Η ροή της κάμερας σταματά σε κάθε έξοδο από την οθόνη.
import { onBeforeUnmount, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'
import { captureFrame, frameBrightness } from '@/ml/imagePrep'
import { useLogStore } from '@/stores/log'

const router = useRouter()
const log = useLogStore()
const video = ref<HTMLVideoElement | null>(null)
const denied = ref(false)
const ready = ref(false)
const dark = ref(false)
const flash = ref(false)
const busy = ref(false)
let stream: MediaStream | null = null
let brightnessTimer: ReturnType<typeof setInterval> | null = null
const sample = document.createElement('canvas')

async function startCamera(): Promise<void> {
  if (!navigator.mediaDevices?.getUserMedia) { denied.value = true; return }
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: 'environment' }, width: { ideal: 1280 }, height: { ideal: 1280 } }, audio: false })
    if (video.value) {
      video.value.srcObject = stream
      await video.value.play()
      ready.value = true
      brightnessTimer = setInterval(() => {
        const b = video.value ? frameBrightness(video.value, sample) : null
        if (b !== null) dark.value = b < 48
      }, 1200)
    }
  } catch {
    denied.value = true                        // NotAllowedError, NotFoundError κ.λπ.: ίδια οθόνη, χωρίς τεχνικούς όρους
  }
}

function stopCamera(): void {
  if (brightnessTimer) clearInterval(brightnessTimer)
  brightnessTimer = null
  stream?.getTracks().forEach((t) => t.stop())
  stream = null
  if (video.value) video.value.srcObject = null
  ready.value = false
}

async function shoot(): Promise<void> {
  if (!video.value || !ready.value || busy.value) return
  busy.value = true
  flash.value = true
  setTimeout(() => { flash.value = false }, 180)
  try {
    const blob = await captureFrame(video.value)
    log.setImage(blob)
    stopCamera()
    router.replace({ name: 'analysis' })
  } catch {
    busy.value = false
  }
}

onMounted(startCamera)
onBeforeUnmount(stopCamera)
</script>

<template>
  <div class="screen screen--dark">
    <TopBar title="Φωτογραφία" back tone="dark" :avatar="false" back-to="/log" />

    <template v-if="!denied">
      <main class="view">
        <span class="hint">Μόνο το πιάτο, χωρίς πρόσωπα</span>
        <div class="frame">
          <video ref="video" class="video" playsinline muted autoplay />
          <span class="corner c1" /><span class="corner c2" /><span class="corner c3" /><span class="corner c4" />
          <span v-if="flash" class="flash" aria-hidden="true" />
        </div>
        <span v-if="dark" class="status" role="status"><Icon name="info" :size="18" />Λίγο σκοτεινά. Δοκίμασε πιο κοντά στο φως.</span>
        <span v-else class="caption">Βάλε το πιάτο μέσα στο πλαίσιο</span>
      </main>
      <footer class="controls">
        <button type="button" class="shutter" aria-label="Λήψη φωτογραφίας" :disabled="!ready || busy" @click="shoot"><span class="shutter__in" /></button>
        <button type="button" class="link" @click="router.replace({ name: 'text' })">Γράψε αντί για φωτογραφία</button>
      </footer>
    </template>

    <template v-else>
      <main class="deniedbody">
        <Icon name="camera" :size="48" :stroke="1.6" />
        <h2 class="t-title">Δεν έχω πρόσβαση στην κάμερα</h2>
        <p class="t-body">Δεν πειράζει. Γράψε ή ψάξε τι έφαγες. Αν θες, μπορείς να δώσεις άδεια από τις ρυθμίσεις του browser.</p>
      </main>
      <footer class="screen__footer darkfooter">
        <AppButton @click="router.replace({ name: 'text' })">Γράψε τι έφαγες</AppButton>
        <AppButton variant="secondary" class="whitebtn" @click="router.replace({ name: 'search' })">Ψάξε φαγητό</AppButton>
      </footer>
    </template>
  </div>
</template>

<style scoped>
.view { flex: 1; min-height: 0; background: var(--color-camera-bg); display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 22px; padding: 16px; }
.hint { background: rgba(0, 0, 0, 0.72); color: #fff; font-size: calc(15px * var(--text-scale)); font-weight: 600; border-radius: 999px; padding: 8px 16px; }
.frame { position: relative; width: min(290px, 80vw); aspect-ratio: 1; display: flex; align-items: center; justify-content: center; }
.video { width: 100%; height: 100%; object-fit: cover; border-radius: 999px; background: #3a3733; }
.corner { position: absolute; width: 44px; height: 44px; border: 3px solid #fff; }
.c1 { top: 0; left: 0; border-right: 0; border-bottom: 0; border-top-left-radius: 14px; }
.c2 { top: 0; right: 0; border-left: 0; border-bottom: 0; border-top-right-radius: 14px; }
.c3 { bottom: 0; left: 0; border-right: 0; border-top: 0; border-bottom-left-radius: 14px; }
.c4 { bottom: 0; right: 0; border-left: 0; border-top: 0; border-bottom-right-radius: 14px; }
.flash { position: absolute; inset: 0; background: rgba(255, 255, 255, 0.35); border-radius: 999px; }
.caption { color: #fff; font-size: calc(14px * var(--text-scale)); }
.status { background: #fff; color: #000; font-size: calc(15px * var(--text-scale)); font-weight: 600; border-radius: 14px; padding: 10px 16px; display: inline-flex; align-items: center; gap: 10px; }
.controls { height: calc(196px + var(--safe-bottom)); padding-bottom: var(--safe-bottom); background: #000; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 14px; flex: none; }
.shutter { width: 78px; height: 78px; border-radius: 999px; border: 5px solid #fff; padding: 5px; background: transparent; }
.shutter:disabled { opacity: 0.5; }
.shutter__in { display: block; width: 100%; height: 100%; border-radius: 999px; background: #fff; }
.shutter:active .shutter__in { background: var(--color-primary); }
.link { background: transparent; border: 0; color: #fff; font-weight: 600; font-size: calc(16px * var(--text-scale)); min-height: 44px; }
.deniedbody { flex: 1; background: var(--color-camera-bg); color: #fff; display: flex; flex-direction: column; justify-content: center; gap: 18px; padding: 28px; }
.darkfooter { background: #000; padding-top: 20px; }
.whitebtn { color: #fff; border-color: #fff; background: transparent; }
</style>
