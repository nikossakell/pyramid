<script setup lang="ts">
// C03 TopBar (ΚΡΑΤΑ): 56 ύψος, τίτλος display 24, προαιρετικό πίσω βέλος, avatar (→ S17), πάντα HelpButton (R7).
// tone='dark' για κάμερα. Το safe-area πάνω προστίθεται εδώ.
import { useRouter } from 'vue-router'
import HelpButton from './HelpButton.vue'
import Icon from './Icon.vue'
import AvatarBadge from './AvatarBadge.vue'
import { useMeStore } from '@/stores/me'

const props = withDefaults(defineProps<{ title?: string; back?: boolean; avatar?: boolean; tone?: 'light' | 'dark'; backTo?: string }>(),
  { title: '', back: false, avatar: true, tone: 'light' })
const router = useRouter()
const me = useMeStore()

function goBack(): void {
  if (props.backTo) router.push(props.backTo)
  else if (window.history.length > 1) router.back()
  else router.push({ name: 'today' })
}
</script>

<template>
  <header class="topbar" :class="{ 'topbar--dark': tone === 'dark', 'topbar--noback': !back }">
    <button v-if="back" type="button" class="iconbtn" aria-label="Πίσω" @click="goBack"><Icon name="back" :size="24" :stroke="2.4" /></button>
    <h1 class="title">{{ title }}</h1>
    <button v-if="avatar" type="button" class="iconbtn iconbtn--avatar" aria-label="Προφίλ και ρυθμίσεις" @click="router.push({ name: 'profile' })">
      <AvatarBadge :avatar-id="me.avatarId" :size="40" />
    </button>
    <HelpButton />
  </header>
</template>

<style scoped>
.topbar {
  display: flex; align-items: center; gap: 8px; height: calc(56px + var(--safe-top)); padding: var(--safe-top) 12px 0 8px;
  background: var(--color-bg); color: var(--color-text); flex: none;
}
.topbar--noback { padding-left: 16px; }
.topbar--dark { background: #000; color: #fff; }
.title { flex: 1; min-width: 0; font-family: var(--font-display); font-weight: 600; font-size: calc(24px * var(--text-scale)); line-height: 30px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.iconbtn { width: 44px; height: 44px; border: 0; background: transparent; border-radius: 999px; color: inherit; display: inline-flex; align-items: center; justify-content: center; padding: 0; flex: none; }
@media (hover: hover) { .iconbtn:hover { background: var(--color-surface); } }
/* expanded: κεφαλίδα σελίδας 72 px, τίτλος αριστερά, HelpButton πάντα δεξιά (R7)· το avatar ζει στο SideNav */
@media (min-width: 1024px) {
  .topbar { height: var(--header-height); padding: 0 32px; gap: 12px; }
  .topbar--noback { padding-left: 32px; }
  .title { font-size: calc(30px * var(--text-scale)); line-height: 36px; }
  .iconbtn--avatar { display: none; }
}
</style>
