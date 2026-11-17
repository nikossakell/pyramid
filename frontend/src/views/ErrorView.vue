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
/* expanded: κάρτα 480 px στο κέντρο (χωρίς SideNav: δημόσια οθόνη) */
@media (min-width: 1024px) {
  .body { flex: 0 0 auto; max-width: 480px; margin-inline: auto; margin-top: auto; padding: 48px 32px 24px; border: 1px solid var(--color-line); border-bottom: 0; border-radius: 24px 24px 0 0; box-shadow: var(--shadow-card); }
  .screen > footer { max-width: 480px; margin-inline: auto; margin-bottom: auto; padding: 0 32px 32px; border: 1px solid var(--color-line); border-top: 0; border-radius: 0 0 24px 24px; box-shadow: var(--shadow-card); }
}
</style>
