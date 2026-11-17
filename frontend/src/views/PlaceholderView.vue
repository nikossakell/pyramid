<script setup lang="ts">
// Tabs «Βοηθός» (S13, Βήμα 5.2) και «Κάρτες» (S14, εκτός φάσης): ουδέτερη οθόνη με HelpButton (R7). Κείμενο placeholder.
// Στο πρώτο άνοιγμα του Βοηθού εμφανίζεται το M08 AIDisclosure (σημάδι στη συσκευή).
import { computed, onMounted, ref } from 'vue'
import TopBar from '@/components/ui/TopBar.vue'
import BottomNav from '@/components/ui/BottomNav.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import AIDisclosure from '@/components/modals/AIDisclosure.vue'

const props = defineProps<{ tab: 'chat' | 'cards' }>()
const title = computed(() => (props.tab === 'chat' ? 'Βοηθός' : 'Κάρτες'))
const M08_KEY = 'pyramid.ai_disclosure_seen'
const m08 = ref(false)

onMounted(() => {
  if (props.tab !== 'chat') return
  try { m08.value = localStorage.getItem(M08_KEY) !== '1' } catch { m08.value = true }
})
function ack(): void {
  m08.value = false
  try { localStorage.setItem(M08_KEY, '1') } catch { /* ignore */ }
}
</script>

<template>
  <div class="screen">
    <TopBar :title="title" />
    <main class="screen__body">
      <EmptyState :icon="tab === 'chat' ? 'chat' : 'cards'" text="[*Αυτή η ενότητα δεν είναι διαθέσιμη ακόμα.]" />
    </main>
    <BottomNav :active="tab" />
    <AIDisclosure :open="m08" @close="ack" />
  </div>
</template>

<style scoped>
/* expanded: η κάρτα (C26) στο κέντρο της περιοχής περιεχομένου */
@media (min-width: 1024px) {
  .screen__body { justify-content: center; align-items: center; }
  .screen__body > * { width: 100%; max-width: 560px; }
}
</style>
