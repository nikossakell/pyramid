<script setup lang="ts">
// S09 Γράψε τι έφαγες (ΚΡΑΤΑ): κείμενο ≤ 300 → POST /meals/text → S08. γ: καμία πρόταση → «Δεν κατάλαβα κάποιο φαγητό».
// δ: σφάλμα server / εκτός σύνδεσης → μαύρο μήνυμα, το κείμενο κρατιέται (μόνο στη μνήμη). Οι ποσότητες δεν εφευρίσκονται.
// Τα «Συνηθισμένα» είναι [*συνηθισμένες φράσεις, εγκεκριμένες]: placeholder μέχρι την έγκριση.
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'
import SlotPicker from '@/components/log/SlotPicker.vue'
import { ApiError } from '@/api/client'
import { analyzeText, TEXT_MAX_LENGTH } from '@/api/meals'
import { useLogStore } from '@/stores/log'

const router = useRouter()
const log = useLogStore()
const busy = ref(false)
const nothing = ref(false)
const failed = ref(false)
const COMMON = ['τοστ με τυρί', 'γάλα με δημητριακά', 'φακές', 'μακαρόνια με κιμά']

const canGo = computed(() => log.text.trim().length > 0 && log.text.length <= TEXT_MAX_LENGTH && !busy.value)

function addCommon(p: string): void {
  log.text = log.text.trim() ? `${log.text.trim()}, ${p}` : p
  nothing.value = false
}

async function go(): Promise<void> {
  if (!canGo.value) return
  busy.value = true
  nothing.value = false
  failed.value = false
  try {
    const res = await analyzeText(log.text.trim())
    if (res.suggestions.length === 0) { nothing.value = true; return }
    log.applySuggestions('text', res.analysis_id, res.suggestions)
    router.replace({ name: 'confirm' })
  } catch (e) {
    if (e instanceof ApiError && e.status === 422) nothing.value = true
    else if (!(e instanceof ApiError && (e.status === 401 || e.status === 403))) failed.value = true
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <div class="screen">
    <TopBar title="Γράψε τι έφαγες" back :avatar="false" back-to="/log" />
    <main class="screen__body body">
      <SlotPicker v-model="log.slot" />
      <label class="lbl" for="meal-text">Τι έφαγες;</label>
      <textarea id="meal-text" v-model="log.text" class="ta" :class="{ 'ta--err': nothing }" :maxlength="TEXT_MAX_LENGTH" rows="5"
                placeholder="π.χ. τοστ με τυρί και ένα πορτοκάλι" autocomplete="off" :aria-describedby="nothing ? 'text-err' : undefined"
                @input="nothing = false; failed = false" />
      <span class="t-caption muted">{{ log.text.length }} / {{ TEXT_MAX_LENGTH }}</span>

      <div v-if="nothing" id="text-err" class="err" role="alert">
        <p class="t-body errline"><Icon name="info" :size="20" /><span>Δεν κατάλαβα κάποιο φαγητό. Δοκίμασε με άλλα λόγια ή ψάξ' το.</span></p>
        <button type="button" class="errbtn" @click="router.replace({ name: 'search' })"><Icon name="search" :size="18" />Ψάξ' το</button>
      </div>
      <div v-else-if="failed" class="banner dark" role="alert">
        <Icon name="warning" :size="20" /><span>Δεν μπορώ να το διαβάσω τώρα. Ψάξε τα φαγητά σου ή δοκίμασε ξανά σε λίγο. Το κείμενό σου κρατήθηκε.</span>
      </div>

      <template v-if="!nothing && !failed">
        <span class="t-label bold">Συνηθισμένα</span>
        <div class="chips">
          <button v-for="p in COMMON" :key="p" type="button" class="chip" @click="addCommon(p)">{{ p }}</button>
        </div>
        <span class="t-caption muted">[*συνηθισμένες φράσεις, εγκεκριμένες]</span>
      </template>
    </main>
    <footer class="screen__footer">
      <template v-if="failed">
        <AppButton @click="router.replace({ name: 'search' })">Ψάξε φαγητό</AppButton>
        <AppButton variant="secondary" @click="go">Δοκίμασε ξανά</AppButton>
      </template>
      <template v-else>
        <AppButton :disabled="!canGo" :loading="busy" @click="go">{{ busy ? 'Διαβάζω τι έγραψες…' : nothing ? 'Δοκίμασε ξανά' : 'Συνέχεια' }}</AppButton>
        <AppButton variant="ghost" @click="router.replace({ name: 'search' })">Ψάξ' το αντί γι' αυτό</AppButton>
      </template>
    </footer>
  </div>
</template>

<style scoped>
.body { gap: 12px; padding: 8px 16px 16px; }
.lbl { font-weight: 700; font-size: calc(15px * var(--text-scale)); }
.ta { width: 100%; min-height: 150px; border-radius: 18px; border: 2px solid var(--color-absent); padding: 14px 16px; font-size: calc(17px * var(--text-scale)); line-height: 1.45; resize: vertical; background: var(--color-bg); }
.ta:focus { outline: none; border-color: var(--color-ink); }
.ta--err { background: var(--color-surface); border-color: var(--color-ink); }
.err { border: 1.5px solid var(--color-ink); border-radius: 16px; padding: 14px; display: flex; flex-direction: column; gap: 12px; }
.errline { display: flex; gap: 10px; align-items: flex-start; }
.errbtn { height: 44px; border-radius: 14px; border: 2px solid var(--color-ink); background: var(--color-bg); color: inherit; font-weight: 600; font-size: calc(15px * var(--text-scale)); display: inline-flex; align-items: center; justify-content: center; gap: 8px; }
.dark { border-radius: 16px; align-items: flex-start; padding: 14px 16px; }
.bold { font-weight: 700; }
.chips { display: flex; flex-wrap: wrap; gap: 8px; }
/* expanded: κεντραρισμένη στήλη 720 px· τα «Συνηθισμένα» σε μία σειρά κάτω από το πεδίο */
@media (min-width: 1024px) {
  .body, .screen > .screen__footer { max-width: 720px; }
  .chips { flex-wrap: nowrap; overflow-x: auto; padding-bottom: 4px; }
  .chip { white-space: nowrap; }
  .ta { min-height: 180px; }
}
</style>
