<script setup lang="ts">
// M05 NotFoodDetected: ΙΔΙΟ κείμενο για κάθε αιτία απόρριψης (422 rejected: όχι φαγητό, ακατάλληλο, σφάλμα). Χωρίς αιτία.
import BottomSheet from '@/components/ui/BottomSheet.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'
defineProps<{ open: boolean }>()
const emit = defineEmits<{ retry: []; text: [] }>()
</script>

<template>
  <BottomSheet :open="open" :dismissible="false" labelled-by="m05-title">
    <span class="ico"><Icon name="camera" :size="30" /></span>
    <h2 id="m05-title" class="t-title">Δεν βλέπω φαγητό σε αυτή τη φωτογραφία</h2>
    <p class="t-body">Δοκίμασε ξανά με το πιάτο στο κέντρο.</p>
    <div class="stack">
      <AppButton @click="emit('retry')">Δοκίμασε ξανά</AppButton>
      <AppButton variant="secondary" @click="emit('text')">Γράψ' το</AppButton>
    </div>
  </BottomSheet>
</template>

<style scoped>
.ico { width: 64px; height: 64px; border-radius: 20px; background: var(--color-surface); display: flex; align-items: center; justify-content: center; }
</style>
