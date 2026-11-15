<script setup lang="ts">
// S20β Γενικό σφάλμα (ΚΡΑΤΑ): «Δεν φταις εσύ.»
import { useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'
const router = useRouter()
</script>

<template>
  <div class="screen">
    <TopBar :avatar="false" />
    <main class="screen__body body">
      <Icon name="warning" :size="56" :stroke="1.6" />
      <h2 class="t-display">Κάτι πήγε στραβά</h2>
      <p class="t-body">Δεν φταις εσύ. Δοκίμασε ξανά σε λίγο.</p>
    </main>
    <footer class="screen__footer">
      <AppButton @click="router.back()">Δοκίμασε ξανά</AppButton>
      <AppButton variant="secondary" @click="router.replace({ name: 'today' })">Πήγαινε στο Σήμερα</AppButton>
    </footer>
  </div>
</template>

<style scoped>
.body { align-items: center; justify-content: center; text-align: center; padding: 28px; gap: 18px; }
</style>
