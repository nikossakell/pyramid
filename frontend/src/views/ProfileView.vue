<script setup lang="ts">
// S17 Προφίλ (ΑΛΛΑΞΕ): χωρίς όνομα, ηλικία, ύψος, βάρος ή στόχους. Avatar (PATCH /me), μέγεθος κειμένου, θέμα,
// μείωση κίνησης (τοπικές προτιμήσεις), Απόρρητο & AI (S18), M10, Έξοδος.
import { ref } from 'vue'
import { RouterLink, useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import BottomNav from '@/components/ui/BottomNav.vue'
import AvatarBadge from '@/components/ui/AvatarBadge.vue'
import AvatarPicker from '@/components/ui/AvatarPicker.vue'
import BottomSheet from '@/components/ui/BottomSheet.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'
import LeaveStudyInfo from '@/components/modals/LeaveStudyInfo.vue'
import { ApiError } from '@/api/client'
import { useAuthStore } from '@/stores/auth'
import { useMeStore } from '@/stores/me'
import { useUiStore, type TextSize, type Theme } from '@/stores/ui'

const router = useRouter()
const auth = useAuthStore()
const me = useMeStore()
const ui = useUiStore()

const avatarOpen = ref(false)
const leaveOpen = ref(false)
const pick = ref<string | null>(me.avatarId)
const saving = ref(false)

const SIZES: { v: TextSize; label: string; px: number }[] = [{ v: 'normal', label: 'Κανονικό', px: 14 }, { v: 'large', label: 'Μεγάλο', px: 16 }, { v: 'xlarge', label: 'Πολύ μεγάλο', px: 18 }]
const THEMES: { v: Theme; label: string }[] = [{ v: 'light', label: 'Φωτεινό' }, { v: 'dark', label: 'Σκοτεινό' }, { v: 'auto', label: 'Αυτόματο' }]
const SECTIONS = [{ id: 'avatar', label: 'Avatar' }, { id: 'text', label: 'Μέγεθος κειμένου' }, { id: 'theme', label: 'Θέμα' },
                  { id: 'motion', label: 'Κίνηση' }, { id: 'more', label: 'Περισσότερα' }]

function openAvatar(): void { pick.value = me.avatarId; avatarOpen.value = true }
async function saveAvatar(): Promise<void> {
  if (!pick.value || pick.value === me.avatarId) { avatarOpen.value = false; return }
  saving.value = true
  try {
    await me.setAvatar(pick.value)
    avatarOpen.value = false
  } catch (e) {
    if (!(e instanceof ApiError && (e.status === 401 || e.status === 403))) ui.toast('Δεν αποθηκεύτηκε. Δοκίμασε ξανά όταν έχεις σύνδεση.', 'error')
  } finally {
    saving.value = false
  }
}
function logout(): void {
  auth.logout()
  me.clear()
  router.replace({ name: 'login' })
}
me.load().catch(() => {})
</script>

<template>
  <div class="screen">
    <TopBar title="Προφίλ" back :avatar="false" back-to="/today" />
    <main class="screen__body body">
      <!-- expanded μόνο: λίστα ενοτήτων αριστερά (διάταξη ρυθμίσεων)· τα links πηγαίνουν στις ενότητες δεξιά -->
      <nav class="setnav" aria-label="Ενότητες ρυθμίσεων">
        <a v-for="s in SECTIONS" :key="s.id" :href="`#${s.id}`" class="setlink">{{ s.label }}</a>
        <RouterLink to="/privacy" class="setlink">Απόρρητο &amp; AI</RouterLink>
      </nav>
      <div class="content">
      <div id="avatar" class="avatarrow">
        <AvatarBadge :avatar-id="me.avatarId" :size="80" />
        <button type="button" class="outbtn" @click="openAvatar">Άλλαξε avatar</button>
      </div>

      <fieldset id="text" class="fs">
        <legend class="legend">Μέγεθος κειμένου</legend>
        <div class="seg" role="radiogroup" aria-label="Μέγεθος κειμένου">
          <button v-for="s in SIZES" :key="s.v" type="button" role="radio" class="segbtn" :class="{ 'segbtn--on': ui.prefs.textSize === s.v }" :aria-checked="ui.prefs.textSize === s.v"
                  :style="{ fontSize: s.px + 'px' }" @click="ui.setPrefs({ textSize: s.v })">{{ s.label }}</button>
        </div>
      </fieldset>

      <fieldset id="theme" class="fs">
        <legend class="legend">Θέμα</legend>
        <div class="seg" role="radiogroup" aria-label="Θέμα">
          <button v-for="t in THEMES" :key="t.v" type="button" role="radio" class="segbtn" :class="{ 'segbtn--on': ui.prefs.theme === t.v }" :aria-checked="ui.prefs.theme === t.v"
                  @click="ui.setPrefs({ theme: t.v })">{{ t.label }}</button>
        </div>
      </fieldset>

      <label id="motion" class="switchrow">
        <span class="txt"><span class="t1">Μείωση κίνησης</span><span class="t-caption muted">Λιγότερα κινούμενα εφέ</span></span>
        <span class="switch" :class="{ 'switch--on': ui.prefs.reduceMotion }">
          <input type="checkbox" role="switch" aria-label="Μείωση κίνησης" :checked="ui.prefs.reduceMotion" @change="ui.setPrefs({ reduceMotion: ($event.target as HTMLInputElement).checked })" />
          <span class="knob" />
        </span>
      </label>

      <nav id="more" class="more" aria-label="Περισσότερα">
        <RouterLink to="/privacy" class="row pressable"><span class="t1">Απόρρητο &amp; AI</span><Icon name="chevron" :size="18" /></RouterLink>
        <button type="button" class="row pressable" @click="leaveOpen = true"><span class="t1">Πώς σταματάω τη συμμετοχή</span><Icon name="chevron" :size="18" /></button>
        <button type="button" class="row pressable" @click="logout"><span class="t1">Έξοδος</span><Icon name="exit" :size="18" /></button>
      </nav>
      </div>
    </main>
    <BottomNav active="none" />

    <BottomSheet :open="avatarOpen" title="Διάλεξε avatar" close-button @close="avatarOpen = false">
      <AvatarPicker v-model="pick" />
      <AppButton :loading="saving" @click="saveAvatar">Εντάξει</AppButton>
    </BottomSheet>
    <LeaveStudyInfo :open="leaveOpen" @close="leaveOpen = false" />
  </div>
</template>

<style scoped>
.body { gap: 16px; padding: 8px 16px 16px; }
.setnav { display: none; }
.content { display: contents; }
/* expanded: διάταξη ρυθμίσεων, αριστερά λίστα ενοτήτων, δεξιά περιεχόμενο έως 720 px */
@media (min-width: 1024px) {
  .body { display: grid; grid-template-columns: 240px minmax(0, 720px); gap: 32px; align-items: start; padding-bottom: 40px; }
  .setnav { display: flex; flex-direction: column; gap: 4px; position: sticky; top: 16px; }
  .setlink { display: flex; align-items: center; min-height: 44px; padding: 0 12px; border-radius: 12px; text-decoration: none; font-weight: 600; font-size: calc(15px * var(--text-scale)); color: var(--color-text-muted); }
  .setlink:hover { background: var(--color-surface); color: var(--color-text); }
  .content { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
  .fs, .switchrow, .more, .avatarrow { scroll-margin-top: 16px; }
}
.avatarrow { display: flex; align-items: center; gap: 16px; }
.outbtn { height: 44px; border-radius: 14px; border: 2px solid var(--color-ink); background: var(--color-bg); color: inherit; font-weight: 600; font-size: calc(15px * var(--text-scale)); padding: 0 16px; }
.fs { border: 0; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 8px; }
.legend { font-weight: 700; font-size: calc(14px * var(--text-scale)); padding: 0 0 8px; }
.seg { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 6px; }
.segbtn { height: 44px; border-radius: 12px; border: 1.5px solid var(--color-absent); background: var(--color-bg); color: inherit; font-size: calc(14px * var(--text-scale)); }
.segbtn--on { background: var(--color-ink); color: var(--color-on-ink); border: 2px solid var(--color-ink); font-weight: 700; }
.switchrow { display: flex; align-items: center; justify-content: space-between; gap: 12px; background: var(--color-surface); border-radius: 16px; padding: 10px 14px; min-height: 60px; cursor: pointer; }
.txt { display: flex; flex-direction: column; gap: 2px; }
.t1 { font-weight: 600; font-size: calc(15px * var(--text-scale)); }
.switch { position: relative; width: 52px; height: 32px; border-radius: 999px; background: var(--color-absent); flex: none; transition: background var(--motion); }
.switch--on { background: var(--color-ink); }
.switch input { position: absolute; inset: 0; width: 100%; height: 100%; opacity: 0; margin: 0; cursor: pointer; }
.knob { position: absolute; top: 4px; left: 4px; width: 24px; height: 24px; border-radius: 999px; background: #fff; transition: transform var(--motion); pointer-events: none; }
.switch--on .knob { transform: translateX(20px); background: var(--color-on-ink); }
.more { border: 1px solid var(--color-line); border-radius: 16px; display: flex; flex-direction: column; }
.row { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 52px; padding: 0 14px; border: 0; border-bottom: 1px solid var(--color-line); background: transparent; color: inherit; text-decoration: none; text-align: left; }
.row:last-child { border-bottom: 0; }
</style>
