<script setup lang="ts">
// M08 AIDisclosure: στο πρώτο άνοιγμα του Βοηθού. Η τελευταία πρόταση περιμένει την απόφαση D10.
import BottomSheet from '@/components/ui/BottomSheet.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'
defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: [] }>()
const LINES = ['Είμαι πρόγραμμα AI, όχι άνθρωπος.', 'Μπορεί να κάνω λάθη.', 'Δεν είμαι γιατρός και δεν σου βάζω δίαιτα.']
</script>

<template>
  <BottomSheet :open="open" :dismissible="false" labelled-by="m08-title">
    <div class="head"><span class="ico"><Icon name="chat" :size="28" /></span><span class="ai">AI</span></div>
    <h2 id="m08-title" class="t-title big">Γνώρισε τον βοηθό</h2>
    <ul class="list">
      <li v-for="l in LINES" :key="l" class="t-body line"><Icon name="check" :size="18" :stroke="2.6" />{{ l }}</li>
      <li class="t-body line"><Icon name="check" :size="18" :stroke="2.6" /><span>Τα μηνύματά σου δεν τα διαβάζει κανείς την ώρα που γράφεις. <span class="muted">[*D10]</span></span></li>
    </ul>
    <AppButton @click="emit('close')">Κατάλαβα</AppButton>
  </BottomSheet>
</template>

<style scoped>
.head { display: flex; align-items: center; gap: 12px; }
.ico { width: 56px; height: 56px; border-radius: 18px; background: var(--color-ink); color: var(--color-on-ink); display: flex; align-items: center; justify-content: center; }
.ai { background: var(--color-secondary); color: #fff; font-weight: 700; font-size: 14px; border-radius: 8px; padding: 3px 10px; }
.big { font-size: calc(28px * var(--text-scale)); }
.list { display: flex; flex-direction: column; gap: 12px; }
.line { display: flex; gap: 12px; align-items: flex-start; }
.line > svg { flex: none; margin-top: 3px; }
</style>
