<script setup lang="ts">
// C02 BottomNav (ΚΡΑΤΑ): 4 tabs + κεντρικό κουμπί καταγραφής. Ενεργό = pill #F14711 και κείμενο 700 (όχι μόνο χρώμα).
import { RouterLink } from 'vue-router'
import Icon from './Icon.vue'

withDefaults(defineProps<{ active?: 'today' | 'history' | 'chat' | 'cards' | 'none'; badge?: boolean }>(), { active: 'none', badge: false })
const tabs = [
  { key: 'today', to: '/today', label: 'Σήμερα', icon: 'home' },
  { key: 'history', to: '/history', label: 'Ιστορικό', icon: 'history' },
] as const
const tabs2 = [
  { key: 'chat', to: '/chat', label: 'Βοηθός', icon: 'chat' },
  { key: 'cards', to: '/cards', label: 'Κάρτες', icon: 'cards' },
] as const
</script>

<template>
  <nav class="nav" aria-label="Κύρια πλοήγηση">
    <RouterLink v-for="t in tabs" :key="t.key" :to="t.to" class="tab" :class="{ 'tab--active': active === t.key }" :aria-current="active === t.key ? 'page' : undefined">
      <span class="pill"><Icon :name="t.icon" :size="22" /></span>
      <span class="label">{{ t.label }}</span>
    </RouterLink>
    <RouterLink to="/log" class="tab tab--log" aria-label="Νέα καταγραφή">
      <span class="logbtn"><Icon name="plus" :size="28" :stroke="2.8" /></span>
      <span class="label label--log">Καταγραφή</span>
    </RouterLink>
    <RouterLink v-for="t in tabs2" :key="t.key" :to="t.to" class="tab" :class="{ 'tab--active': active === t.key }" :aria-current="active === t.key ? 'page' : undefined">
      <span class="pill">
        <Icon :name="t.icon" :size="22" />
        <span v-if="t.key === 'cards' && badge" class="badge" aria-label="Νέες κάρτες" />
      </span>
      <span class="label">{{ t.label }}</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
.nav { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); height: calc(88px + var(--safe-bottom)); padding: 6px 8px calc(22px + var(--safe-bottom)); background: var(--color-bg); border-top: 1px solid var(--color-line); flex: none; }
.tab { display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 3px; height: 56px; text-decoration: none; color: var(--color-text-muted); }
.tab--active { color: var(--color-text); }
.pill { position: relative; width: 56px; height: 30px; border-radius: 999px; display: flex; align-items: center; justify-content: center; }
.tab--active .pill { background: var(--color-primary); color: #000; }
.label { font-size: calc(13px * var(--text-scale)); font-weight: 500; }
.tab--active .label { font-weight: 700; }
.tab--log { color: var(--color-text); }
.logbtn { width: 60px; height: 60px; border-radius: 999px; background: var(--color-primary); color: #000; border: 4px solid var(--color-bg); display: flex; align-items: center; justify-content: center; margin-top: -22px; box-shadow: var(--shadow-card); }
.label--log { font-weight: 700; }
.badge { position: absolute; top: 2px; right: 10px; width: 12px; height: 12px; border-radius: 999px; background: var(--color-secondary); border: 2px solid var(--color-bg); }
</style>
