<script setup lang="ts">
// M10 LeaveStudyInfo (από S17 / S18): η εφαρμογή δεν διαγράφει τίποτα μόνη της· η ανάκληση γίνεται μέσω της ομάδας.
// «Επικοινωνία με την ομάδα» ανοίγει το M01 (εκεί είναι τα [*στοιχεία επικοινωνίας]).
import BottomSheet from '@/components/ui/BottomSheet.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { useUiStore } from '@/stores/ui'
defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const ui = useUiStore()
function contact(): void { emit('close'); ui.helpOpen = true }
</script>

<template>
  <BottomSheet :open="open" labelled-by="m10-title" @close="emit('close')">
    <h2 id="m10-title" class="t-title">Πώς σταματάω τη συμμετοχή</h2>
    <p class="t-body">Μπορείς να σταματήσεις όποτε θέλεις, χωρίς να εξηγήσεις γιατί.</p>
    <div class="how">
      <span class="t-label bold">Πώς γίνεται</span>
      <ol class="steps">
        <li>Μίλα με την ερευνητική ομάδα. <span class="muted">[*στοιχεία επικοινωνίας]</span></li>
        <li>Συμπληρώνεται το έντυπο ανάκλησης.</li>
      </ol>
    </div>
    <p class="t-label muted">Η εφαρμογή δεν διαγράφει τίποτα μόνη της. Η ανάκληση γίνεται μέσω της ομάδας.</p>
    <AppButton @click="contact">Επικοινωνία με την ομάδα</AppButton>
    <AppButton variant="ghost" @click="emit('close')">Κλείσε</AppButton>
  </BottomSheet>
</template>

<style scoped>
.how { background: var(--color-surface); border-radius: 16px; padding: 14px; display: flex; flex-direction: column; gap: 8px; }
.bold { font-weight: 700; }
.steps { list-style: decimal; padding-left: 20px; display: flex; flex-direction: column; gap: 6px; font-size: calc(15px * var(--text-scale)); line-height: 1.45; }
</style>
