<script setup lang="ts">
// M04 CameraPermission: πριν από το αίτημα άδειας του browser. Κείμενο φωτογραφίας κατά mockups_delta §3 (D1 = server).
import BottomSheet from '@/components/ui/BottomSheet.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'
import { PRIVACY_PHOTO_APPROVAL, PRIVACY_PHOTO_COPY } from '@/lib/copy'

defineProps<{ open: boolean }>()
const emit = defineEmits<{ close: []; continue: []; text: [] }>()
</script>

<template>
  <BottomSheet :open="open" labelled-by="m04-title" @close="emit('close')">
    <span class="ico"><Icon name="camera" :size="30" /></span>
    <h2 id="m04-title" class="t-title">Θα χρειαστώ την κάμερα</h2>
    <p class="t-body">Για να δω τι έχει το πιάτο σου. Φωτογράφισε μόνο το φαγητό, χωρίς πρόσωπα.</p>
    <div class="privacy">
      <span class="copy">{{ PRIVACY_PHOTO_COPY }}</span>
      <span class="t-caption muted">{{ PRIVACY_PHOTO_APPROVAL }}</span>
    </div>
    <div class="stack">
      <AppButton @click="emit('continue')">Συνέχεια</AppButton>
      <AppButton variant="ghost" @click="emit('text')">Θα γράψω αντί για φωτογραφία</AppButton>
    </div>
  </BottomSheet>
</template>

<style scoped>
.ico { width: 64px; height: 64px; border-radius: 20px; background: var(--color-surface); display: flex; align-items: center; justify-content: center; }
.privacy { border: 1.5px dashed var(--color-ink); border-radius: 12px; padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; }
.copy { font-weight: 700; font-size: calc(15px * var(--text-scale)); line-height: 1.4; }
</style>
