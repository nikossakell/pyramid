<script setup lang="ts">
// Sheet από κάτω (M01, M02, M04–M06, M08, M10, S05): radius 28, λαβή, scrim που ΞΕΚΙΝΑ ΚΑΤΩ ΑΠΟ ΤΟ TOPBAR, ώστε το HelpButton
// να μένει ορατό (R7). Esc / scrim κλείνουν (εκτός αν dismissible=false). Focus trap με Tab και επιστροφή της εστίασης
// στο στοιχείο που το άνοιξε, σε κάθε πλάτος.
// expanded (≥ 1024): το component αποφασίζει μόνο του τη μορφή: κεντραρισμένο dialog (max 560 px) ή, με tone='help',
// συρτάρι 400 px δεξιά (M01), πάνω από όλα. Σε compact/medium η διάταξη είναι η ίδια με πριν.
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Icon from './Icon.vue'

const props = withDefaults(defineProps<{ open: boolean; title?: string; dismissible?: boolean; tone?: 'default' | 'help'; closeButton?: boolean; labelledBy?: string }>(),
  { title: '', dismissible: true, tone: 'default', closeButton: false })
const emit = defineEmits<{ close: [] }>()
const panel = ref<HTMLElement | null>(null)
let opener: HTMLElement | null = null

const FOCUSABLE = 'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])'

function focusables(): HTMLElement[] {
  return panel.value ? Array.from(panel.value.querySelectorAll<HTMLElement>(FOCUSABLE)).filter((el) => el.offsetParent !== null || el === document.activeElement) : []
}

function onKey(e: KeyboardEvent): void {
  if (!props.open) return
  if (e.key === 'Escape' && props.dismissible) { emit('close'); return }
  if (e.key !== 'Tab' || !panel.value) return
  const items = focusables()
  if (items.length === 0) { e.preventDefault(); panel.value.focus(); return }
  const first = items[0], last = items[items.length - 1]
  const active = document.activeElement as HTMLElement | null
  if (e.shiftKey && (active === first || !panel.value.contains(active))) { e.preventDefault(); last.focus() }
  else if (!e.shiftKey && active === last) { e.preventDefault(); first.focus() }
}

onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
watch(() => props.open, async (o) => {
  if (o) {
    opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    await nextTick()
    requestAnimationFrame(() => panel.value?.focus())
  } else if (opener && document.contains(opener)) {
    opener.focus()
    opener = null
  }
}, { immediate: true })
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="open" class="layer" :class="{ 'layer--help': tone === 'help' }">
        <div class="scrim" @click="dismissible && emit('close')" />
        <div ref="panel" class="panel" :class="{ 'panel--help': tone === 'help' }" role="dialog" aria-modal="true" tabindex="-1"
             :aria-labelledby="labelledBy" :aria-label="labelledBy ? undefined : title || undefined">
          <div class="handle" aria-hidden="true" />
          <div v-if="title || closeButton" class="head">
            <h2 v-if="title" class="t-title">{{ title }}</h2>
            <span v-else />
            <button v-if="closeButton" type="button" class="close" aria-label="Κλείσε" @click="emit('close')"><Icon name="x" :size="22" :stroke="2.4" /></button>
          </div>
          <slot />
        </div>
      </div>
    </Transition>
  </Teleport>
</template>

<style scoped>
.layer { position: fixed; inset: 0; z-index: 50; display: flex; flex-direction: column; justify-content: flex-end; }
.scrim { position: absolute; left: 0; right: 0; bottom: 0; top: calc(56px + var(--safe-top)); background: var(--color-scrim); }
.panel { position: relative; background: var(--color-bg); color: var(--color-text); border-radius: 28px 28px 0 0; padding: 12px 16px calc(36px + var(--safe-bottom)); display: flex; flex-direction: column; gap: 16px; box-shadow: var(--shadow-sheet); max-height: calc(100dvh - 56px - var(--safe-top) - 8px); overflow-y: auto; outline: none; }
.panel--help { background: var(--color-help-surface); color: #000; }
.handle { width: 40px; height: 5px; border-radius: 999px; background: var(--color-line); align-self: center; }
.panel--help .handle { background: var(--color-help-handle); }
.head { display: flex; align-items: center; justify-content: space-between; gap: 12px; }
.close { width: 44px; height: 44px; border-radius: 999px; border: 0; background: var(--color-surface); display: flex; align-items: center; justify-content: center; flex: none; }
.panel--help .close { background: #fff; color: #000; }
@media (hover: hover) { .close:hover { background: var(--color-surface-pressed); } }
.sheet-enter-active, .sheet-leave-active { transition: opacity var(--motion); }
.sheet-enter-active .panel, .sheet-leave-active .panel { transition: transform var(--motion) ease-out; }
.sheet-enter-from, .sheet-leave-to { opacity: 0; }
.sheet-enter-from .panel, .sheet-leave-to .panel { transform: translateY(24px); }

/* medium: το sheet μένει, περιορισμένο στο πλάτος της στήλης */
@media (min-width: 600px) and (max-width: 1023.98px) {
  .panel { width: 100%; max-width: var(--content-max-medium); margin-inline: auto; }
}

/* expanded: dialog στο κέντρο (max 560 px)· το scrim ξεκινά κάτω από την κεφαλίδα, ώστε το HelpButton να μένει ορατό (R7) */
@media (min-width: 1024px) {
  .layer { align-items: center; justify-content: center; padding: 24px; }
  .scrim { top: var(--header-height); }
  .panel { width: 100%; max-width: var(--dialog-max); border-radius: 24px; padding: 20px 24px 24px; max-height: calc(100dvh - var(--header-height) - 48px); }
  .handle { display: none; }
  .sheet-enter-from .panel, .sheet-leave-to .panel { transform: translateY(12px); }
  /* M01: συρτάρι δεξιά 400 px, πάνω από όλα (και πάνω από το SideNav) */
  .layer--help { align-items: stretch; justify-content: flex-end; padding: 0; z-index: 80; }
  .layer--help .scrim { top: 0; }
  .layer--help .panel { max-width: var(--drawer-width); height: 100dvh; max-height: none; border-radius: 0; padding: 24px 24px 32px; box-shadow: -8px 0 32px rgba(0, 0, 0, 0.16); }
  .sheet-enter-from .layer--help .panel, .sheet-leave-to .layer--help .panel, .layer--help.sheet-enter-from .panel, .layer--help.sheet-leave-to .panel { transform: translateX(24px); }
}
</style>
