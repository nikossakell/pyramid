<script setup lang="ts">
// C30 DayCompletePrompt (ΑΠΟΦΑΣΗ, mockups_delta §1): «Κατέγραψες όλα τα σημερινά;» → POST /days/{day}/complete.
// Καταστάσεις: ερώτηση · δηλώθηκε («Εντάξει, η μέρα κλείνει.») · δεν εμφανίζεται χωρίς γεύμα (το κρίνει ο γονέας).
// Χωρίς επιβράβευση, χωρίς ενοχή: το «Όχι ακόμα» απλώς κρύβει την κάρτα για σήμερα.
import { ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'

const props = defineProps<{ completed: boolean; day: string }>()
const emit = defineEmits<{ confirm: [] }>()

const KEY = 'pyramid.day_prompt_dismissed'
function dismissedToday(): boolean {
  try { return sessionStorage.getItem(KEY) === props.day } catch { return false }
}
const hidden = ref(dismissedToday())
const busy = ref(false)

function later(): void {
  hidden.value = true
  try { sessionStorage.setItem(KEY, props.day) } catch { /* ignore */ }
}
async function yes(): Promise<void> {
  busy.value = true
  try { emit('confirm') } finally { busy.value = false }
}
</script>

<template>
  <div v-if="completed" class="card done" role="status">
    <span class="ico"><Icon name="check" :size="18" :stroke="3" /></span>
    <span class="t-body">Εντάξει, η μέρα κλείνει.</span>
  </div>
  <section v-else-if="!hidden" class="card ask" aria-labelledby="day-complete-q">
    <h2 id="day-complete-q" class="q">Κατέγραψες όλα τα σημερινά;</h2>
    <div class="btns">
      <AppButton :loading="busy" @click="yes">Ναι, αυτά ήταν</AppButton>
      <AppButton variant="ghost" @click="later">Όχι ακόμα</AppButton>
    </div>
  </section>
</template>

<style scoped>
.ask { border-radius: 18px; display: flex; flex-direction: column; gap: 12px; }
.q { font-weight: 700; font-size: calc(16px * var(--text-scale)); }
.btns { display: flex; flex-direction: column; gap: 4px; }
.done { border-radius: 18px; display: flex; align-items: center; gap: 12px; background: var(--color-surface); border-color: transparent; }
.ico { width: 32px; height: 32px; border-radius: 999px; background: var(--color-positive); color: #fff; display: inline-flex; align-items: center; justify-content: center; flex: none; }
</style>
