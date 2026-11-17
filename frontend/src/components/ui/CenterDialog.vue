<script setup lang="ts">
// Κεντρικό alertdialog (M07 DeleteMeal, M09 SessionExpired): radius 24, scrim κάτω από το TopBar (expanded: κάτω από την
// κεφαλίδα). Δεν κλείνει με Esc/scrim (ο χρήστης απαντά με κουμπί)· εστίαση μέσα στο πλαίσιο και επιστροφή στο στοιχείο
// που το άνοιξε. Το Tab μένει μέσα στο πλαίσιο.
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'

const props = withDefaults(defineProps<{ open: boolean; labelledBy: string; describedBy?: string }>(), {})
const box = ref<HTMLElement | null>(null)
let opener: HTMLElement | null = null
const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])'

function onKey(e: KeyboardEvent): void {
  if (!props.open || e.key !== 'Tab' || !box.value) return
  const items = Array.from(box.value.querySelectorAll<HTMLElement>(FOCUSABLE))
  if (!items.length) { e.preventDefault(); box.value.focus(); return }
  const first = items[0], last = items[items.length - 1]
  const active = document.activeElement as HTMLElement | null
  if (e.shiftKey && (active === first || !box.value.contains(active))) { e.preventDefault(); last.focus() }
  else if (!e.shiftKey && active === last) { e.preventDefault(); first.focus() }
}
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
watch(() => props.open, async (o) => {
  if (o) {
    opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    await nextTick()
    requestAnimationFrame(() => box.value?.focus())
  } else if (opener && document.contains(opener)) {
    opener.focus()
    opener = null
  }
}, { immediate: true })
</script>

<template>
  <Teleport to="body">
    <Transition name="dlg">
      <div v-if="open" class="layer">
        <div class="scrim" />
        <div ref="box" class="box" role="alertdialog" aria-modal="true" tabindex="-1" :aria-labelledby="labelledBy" :aria-describedby="describedBy">
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.layer { position: fixed; inset: 0; z-index: 60; display: flex; align-items: center; justify-content: center; padding: 20px; }
.scrim { position: absolute; left: 0; right: 0; bottom: 0; top: calc(56px + var(--safe-top)); background: var(--color-scrim); }
.box { position: relative; width: 100%; max-width: 358px; background: var(--color-bg); color: var(--color-text); border-radius: 24px; padding: 24px 20px; display: flex; flex-direction: column; gap: 14px; box-shadow: var(--shadow-sheet); outline: none; }
.dlg-enter-active, .dlg-leave-active { transition: opacity var(--motion); }
.dlg-enter-from, .dlg-leave-to { opacity: 0; }
@media (min-width: 1024px) {
  .scrim { top: var(--header-height); }
  .box { max-width: 420px; padding: 28px 24px 24px; }
}
</style>
