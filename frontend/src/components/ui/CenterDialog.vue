<script setup lang="ts">
// Κεντρικό alertdialog (M07 DeleteMeal, M09 SessionExpired): radius 24, scrim κάτω από το TopBar.
withDefaults(defineProps<{ open: boolean; labelledBy: string; describedBy?: string }>(), {})
</script>

<template>
  <Teleport to="body">
    <Transition name="dlg">
      <div v-if="open" class="layer">
        <div class="scrim" />
        <div class="box" role="alertdialog" aria-modal="true" :aria-labelledby="labelledBy" :aria-describedby="describedBy">
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.layer { position: fixed; inset: 0; z-index: 60; display: flex; align-items: center; justify-content: center; padding: 20px; }
.scrim { position: absolute; left: 0; right: 0; bottom: 0; top: calc(56px + var(--safe-top)); background: var(--color-scrim); }
.box { position: relative; width: 100%; max-width: 358px; background: var(--color-bg); color: var(--color-text); border-radius: 24px; padding: 24px 20px 20px; display: flex; flex-direction: column; gap: 14px; box-shadow: var(--shadow-sheet); }
.dlg-enter-active, .dlg-leave-active { transition: opacity var(--motion); }
.dlg-enter-from, .dlg-leave-to { opacity: 0; }
</style>
