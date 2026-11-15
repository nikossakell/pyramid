<script setup lang="ts">
// S03 Πρώτη χρήση (ΚΡΑΤΑ): 4 βήματα με επιστροφή + επιλογή avatar (C06). Δεν αντικαθιστά τη γραπτή συναίνεση.
// Βήμα 3: κείμενο φωτογραφίας κατά mockups_delta §3 (D1 = server)· η φράση «δεν φεύγει από το κινητό» δεν υπάρχει.
// «Ξεκίνα» → PATCH /me {avatar_id}, σημάδι onboarding στη συσκευή, S04.
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import StepDots from '@/components/ui/StepDots.vue'
import AppButton from '@/components/ui/AppButton.vue'
import AvatarPicker from '@/components/ui/AvatarPicker.vue'
import PyramidMark from '@/components/ui/PyramidMark.vue'
import Icon from '@/components/ui/Icon.vue'
import { AVATARS } from '@/components/ui/avatars'
import { ApiError, OFFLINE } from '@/api/client'
import { PRIVACY_PHOTO_APPROVAL, PRIVACY_PHOTO_COPY } from '@/lib/copy'
import { useAuthStore } from '@/stores/auth'
import { useMeStore } from '@/stores/me'
import { useUiStore } from '@/stores/ui'

const router = useRouter()
const auth = useAuthStore()
const me = useMeStore()
const ui = useUiStore()

const STEPS = [
  { title: 'Τι κάνει το PYRAMID', text: 'Κατέγραψε τι τρως, μάθε για το φαγητό, κέρδισε κάρτες.' },
  { title: 'Τι δεν κάνει', text: 'Δεν είναι γιατρός και δεν σου βάζει δίαιτα.' },
  { title: 'Φωτογραφίες', text: 'Φωτογράφισε μόνο το πιάτο, χωρίς πρόσωπα.' },
  { title: 'Βοηθός AI και βοήθεια', text: 'Ο βοηθός είναι AI, όχι άνθρωπος. Μπορεί να κάνει λάθη. Αν χρειαστείς βοήθεια, πάτα εδώ.' },
]

const step = ref(1)                        // 1–4 κείμενα, 5 = avatar
const avatar = ref<string | null>(null)
const busy = ref(false)
const isAvatarStep = computed(() => step.value === 5)

onMounted(async () => {
  try { await me.load() } catch { /* offline: συνεχίζουμε */ }
  avatar.value = me.avatarId ?? AVATARS[0].id
})

async function finish(): Promise<void> {
  busy.value = true
  try {
    if (avatar.value && avatar.value !== me.avatarId) await me.setAvatar(avatar.value)
    auth.markOnboarded()
    router.replace({ name: 'today' })
  } catch (e) {
    if (e instanceof ApiError && e.status === OFFLINE) ui.toast('Χρειάζεται σύνδεση για να αποθηκευτεί το avatar. Δοκίμασε ξανά.', 'error')
    else if (!(e instanceof ApiError && (e.status === 401 || e.status === 403))) ui.toast('Κάτι πήγε στραβά. Δοκίμασε ξανά σε λίγο.', 'error')
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="screen">
    <TopBar :avatar="false" />
    <span v-if="step === 4" class="help-ring" aria-hidden="true" />
    <main class="screen__body body">
      <template v-if="!isAvatarStep">
        <StepDots :total="4" :current="step" />

        <div class="hero" :class="{ 'hero--dark': step === 3 }">
          <template v-if="step === 1">
            <span class="bubble" style="background: var(--color-primary); color: #000"><Icon name="camera" :size="40" :stroke="1.8" /></span>
            <span class="bubble" style="background: var(--color-positive); color: #000"><Icon name="leaf" :size="40" :stroke="1.8" /></span>
            <span class="bubble" style="background: var(--color-secondary); color: #fff"><Icon name="cards" :size="40" :stroke="1.8" /></span>
          </template>
          <PyramidMark v-else-if="step === 2" :height="144" />
          <span v-else-if="step === 3" class="frame"><Icon name="camera" :size="64" :stroke="1.4" /></span>
          <template v-else>
            <span class="ai"><Icon name="chat" :size="52" :stroke="1.8" /></span>
            <span class="ai-tag">AI</span>
          </template>
        </div>

        <h2 class="t-display title">{{ STEPS[step - 1].title }}</h2>
        <p class="lead">{{ STEPS[step - 1].text }}</p>
        <div v-if="step === 3" class="privacy">
          <span class="privacy__copy">{{ PRIVACY_PHOTO_COPY }}</span>
          <span class="t-caption muted">{{ PRIVACY_PHOTO_APPROVAL }}</span>
        </div>
      </template>

      <template v-else>
        <h2 class="t-display title">Διάλεξε avatar</h2>
        <p class="lead muted">Θα εμφανίζεται πάνω δεξιά. Μπορείς να το αλλάξεις όποτε θες.</p>
        <AvatarPicker v-model="avatar" />
      </template>
    </main>

    <footer class="screen__footer row">
      <AppButton v-if="step > 1" variant="secondary" :block="false" class="back" @click="step--">Πίσω</AppButton>
      <AppButton v-if="!isAvatarStep" @click="step++">Επόμενο</AppButton>
      <AppButton v-else :loading="busy" @click="finish">Ξεκίνα</AppButton>
    </footer>
  </div>
</template>

<style scoped>
.body { padding: 12px 20px 16px; gap: 20px; }
.hero { background: var(--color-surface); border-radius: 28px; height: 240px; display: flex; align-items: center; justify-content: center; gap: 0; flex: none; position: relative; }
.hero--dark { background: var(--color-camera-bg); color: #fff; }
.bubble { width: 92px; height: 92px; border-radius: 999px; border: 4px solid var(--color-surface); display: flex; align-items: center; justify-content: center; margin: 0 -10px; }
.frame { width: 170px; height: 170px; border: 3px dashed rgba(255, 255, 255, 0.7); border-radius: 20px; display: flex; align-items: center; justify-content: center; }
.ai { width: 104px; height: 104px; border-radius: 32px; background: var(--color-ink); color: var(--color-on-ink); display: flex; align-items: center; justify-content: center; }
.ai-tag { position: absolute; right: 24px; bottom: 22px; background: var(--color-secondary); color: #fff; font-weight: 700; font-size: 15px; border-radius: 8px; padding: 4px 12px; }
.title { font-size: calc(30px * var(--text-scale)); }
.lead { font-size: calc(17px * var(--text-scale)); line-height: 1.5; }
.privacy { border: 1.5px dashed var(--color-ink); border-radius: 12px; padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; }
.privacy__copy { font-weight: 700; font-size: calc(15px * var(--text-scale)); line-height: 1.4; }
.row { flex-direction: row; gap: 10px; }
.back { width: 120px; flex: none; }
.help-ring { position: absolute; top: calc(var(--safe-top) + 2px); right: 4px; width: 148px; height: 56px; border: 3px dashed var(--color-ink); border-radius: 999px; pointer-events: none; }
</style>
