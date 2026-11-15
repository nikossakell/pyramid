<script setup lang="ts">
// Sheet από κάτω (M01, M02, M04–M06, M08, M10, S05): radius 28, λαβή, scrim που ΞΕΚΙΝΑ ΚΑΤΩ ΑΠΟ ΤΟ TOPBAR, ώστε το HelpButton
// να μένει ορατό (R7). Esc / scrim κλείνουν (εκτός αν dismissible=false).
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import Icon from './Icon.vue'

const props = withDefaults(defineProps<{ open: boolean; title?: string; dismissible?: boolean; tone?: 'default' | 'help'; closeButton?: boolean; labelledBy?: string }>(),
  { title: '', dismissible: true, tone: 'default', closeButton: false })
const emit = defineEmits<{ close: [] }>()
const panel = ref<HTMLElement | null>(null)

function onKey(e: KeyboardEvent): void { if (e.key === 'Escape' && props.dismissible && props.open) emit('close') }
onMounted(() => document.addEventListener('keydown', onKey))
onBeforeUnmount(() => document.removeEventListener('keydown', onKey))
watch(() => props.open, (o) => { if (o) requestAnimationFrame(() => panel.value?.focus()) })
</script>

<template>
  <Teleport to="body">
    <Transition name="sheet">
      <div v-if="open" class="layer">
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
.sheet-enter-active, .sheet-leave-active { transition: opacity var(--motion); }
.sheet-enter-active .panel, .sheet-leave-active .panel { transition: transform var(--motion) ease-out; }
.sheet-enter-from, .sheet-leave-to { opacity: 0; }
.sheet-enter-from .panel, .sheet-leave-to .panel { transform: translateY(24px); }
</style>
