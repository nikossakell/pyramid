<script setup lang="ts">
// S21 «Δεν έχει ανοίξει ακόμα» (ΝΕΟ, mockups_delta §6): ομάδα ελέγχου πριν το CONTROL_ACCESS_FROM. Χωρίς τη λέξη «ομάδα
// ελέγχου». Ο server δεν δίνει ημερομηνία (403 not_yet_available): μένει placeholder.
import TopBar from '@/components/ui/TopBar.vue'
import PyramidMark from '@/components/ui/PyramidMark.vue'
import AppButton from '@/components/ui/AppButton.vue'
import { useRouter } from 'vue-router'
const router = useRouter()
</script>

<template>
  <div class="screen">
    <TopBar :avatar="false" />
    <main class="screen__body body">
      <PyramidMark :height="120" />
      <h2 class="t-display headline">Η εφαρμογή θα ανοίξει για σένα [*ημερομηνία].</h2>
      <p class="t-body">Ευχαριστούμε που συμμετέχεις! <span class="muted">[*προς έγκριση]</span></p>
    </main>
    <footer class="screen__footer">
      <AppButton variant="secondary" @click="router.replace({ name: 'login' })">Πίσω στην είσοδο</AppButton>
    </footer>
  </div>
</template>

<style scoped>
.body { align-items: center; text-align: center; padding: 24px; gap: 22px; justify-content: center; }
.headline { font-size: calc(30px * var(--text-scale)); line-height: 1.2; }
/* expanded: κάρτα 480 px στο κέντρο (χωρίς SideNav) */
@media (min-width: 1024px) {
  .body { flex: 0 0 auto; max-width: 480px; margin-inline: auto; margin-top: auto; padding: 48px 32px 24px; border: 1px solid var(--color-line); border-bottom: 0; border-radius: 24px 24px 0 0; box-shadow: var(--shadow-card); }
  .screen > footer { max-width: 480px; margin-inline: auto; margin-bottom: auto; padding: 0 32px 32px; border: 1px solid var(--color-line); border-top: 0; border-radius: 0 0 24px 24px; box-shadow: var(--shadow-card); }
}
</style>
