<script setup lang="ts">
// S19 Τέλος μελέτης (ΚΡΑΤΑ): και όταν ο server απαντά 403 {"study_ended": true} σε οποιοδήποτε αίτημα.
import TopBar from '@/components/ui/TopBar.vue'
import PyramidMark from '@/components/ui/PyramidMark.vue'
import Icon from '@/components/ui/Icon.vue'
</script>

<template>
  <div class="screen">
    <TopBar :avatar="false" />
    <main class="screen__body body">
      <PyramidMark :height="120" />
      <h2 class="t-display headline">Οι 12 εβδομάδες τελείωσαν. Ευχαριστούμε!</h2>
      <div class="card card--surface meet">
        <Icon name="clock" :size="28" />
        <div class="stack">
          <span class="t-heading">Μην ξεχάσεις τη συνάντηση</span>
          <span class="t-body">Θα συμπληρώσεις τα τελευταία ερωτηματολόγια. [*ημερομηνία και τόπος]</span>
        </div>
      </div>
      <p class="muted t-body">[*Τι γίνεται με την πρόσβαση μετά τη μελέτη: απόφαση της ομάδας]</p>
    </main>
  </div>
</template>

<style scoped>
.body { align-items: center; text-align: center; padding: 24px; gap: 22px; }
.headline { font-size: calc(34px * var(--text-scale)); line-height: 1.18; }
.meet { width: 100%; display: flex; gap: 12px; align-items: flex-start; text-align: left; }
</style>
