<script setup lang="ts">
// SideNav (expanded ≥ 1024 μόνο· αντικαθιστά το C02 BottomNav): 240 px σταθερό αριστερά. Λογότυπο, «+ Καταγραφή» (ίδιο χρώμα
// με το κεντρικό κουμπί του BottomNav), Σήμερα, Ιστορικό, Βοηθός, Κάρτες (ίδια σειρά), και κάτω το Προφίλ με avatar.
// Ενεργό = pill #F14711 + κείμενο 700 + aria-current="page". Ίδια δεδομένα: badge καρτών από το meals store.
import { RouterLink } from 'vue-router'
import Icon from './Icon.vue'
import PyramidMark from './PyramidMark.vue'
import AvatarBadge from './AvatarBadge.vue'
import { useMeStore } from '@/stores/me'
import { useMealsStore } from '@/stores/meals'

export type NavKey = 'today' | 'history' | 'chat' | 'cards' | 'profile' | 'log' | 'none'
withDefaults(defineProps<{ active?: NavKey }>(), { active: 'none' })
const me = useMeStore()
const meals = useMealsStore()

const ITEMS = [
  { key: 'today', to: '/today', label: 'Σήμερα', icon: 'home' },
  { key: 'history', to: '/history', label: 'Ιστορικό', icon: 'history' },
  { key: 'chat', to: '/chat', label: 'Βοηθός', icon: 'chat' },
  { key: 'cards', to: '/cards', label: 'Κάρτες', icon: 'cards' },
] as const
</script>

<template>
  <nav class="side" aria-label="Κύρια πλοήγηση">
    <RouterLink to="/today" class="logo" aria-label="PYRAMID, Σήμερα"><PyramidMark :height="34" wordmark :word-size="30" /></RouterLink>

    <RouterLink to="/log" class="log pressable" :aria-current="active === 'log' ? 'page' : undefined">
      <Icon name="plus" :size="24" :stroke="2.8" /><span>Καταγραφή</span>
    </RouterLink>

    <ul class="items">
      <li v-for="it in ITEMS" :key="it.key">
        <RouterLink :to="it.to" class="item pressable" :class="{ 'item--active': active === it.key }" :aria-current="active === it.key ? 'page' : undefined">
          <span class="pill">
            <Icon :name="it.icon" :size="22" />
            <span v-if="it.key === 'cards' && meals.unopenedCards > 0" class="newdot" aria-label="Νέες κάρτες" />
          </span>
          <span class="label">{{ it.label }}</span>
        </RouterLink>
      </li>
    </ul>

    <RouterLink to="/profile" class="item item--profile pressable" :class="{ 'item--active': active === 'profile' }" :aria-current="active === 'profile' ? 'page' : undefined">
      <AvatarBadge :avatar-id="me.avatarId" :size="36" />
      <span class="label">Προφίλ</span>
    </RouterLink>
  </nav>
</template>

<style scoped>
.side { position: fixed; top: 0; left: 0; bottom: 0; width: var(--sidenav-width); display: flex; flex-direction: column; gap: 8px; padding: 20px 16px 20px; background: var(--color-bg); border-right: 1px solid var(--color-line); z-index: 40; }
.logo { display: flex; align-items: center; min-height: 44px; padding: 0 8px 12px; text-decoration: none; color: inherit; }
.log { display: flex; align-items: center; justify-content: center; gap: 10px; height: 52px; border-radius: 16px; background: var(--color-primary); color: #000; font-weight: 700; font-size: calc(16px * var(--text-scale)); text-decoration: none; margin-bottom: 12px; box-shadow: var(--shadow-card); }
.log[aria-current='page'] { outline: 3px solid var(--color-ink); outline-offset: 2px; }
.items { display: flex; flex-direction: column; gap: 4px; }
.item { display: flex; align-items: center; gap: 12px; min-height: 48px; padding: 4px 8px; border-radius: 14px; text-decoration: none; color: var(--color-text-muted); }
.item--active { color: var(--color-text); }
@media (hover: hover) { .item:hover { background: var(--color-surface); filter: none; } }
.pill { position: relative; width: 56px; height: 32px; border-radius: 999px; display: flex; align-items: center; justify-content: center; flex: none; }
.item--active .pill { background: var(--color-primary); color: #000; }
.label { font-size: calc(15px * var(--text-scale)); font-weight: 500; }
.item--active .label { font-weight: 700; }
/* όχι «.badge»: είναι η root κλάση του AvatarBadge και τα scoped styles πιάνουν και τη ρίζα του παιδιού */
.newdot { position: absolute; top: 1px; right: 10px; width: 12px; height: 12px; border-radius: 999px; background: var(--color-secondary); border: 2px solid var(--color-bg); }
.item--profile { margin-top: auto; padding-left: 10px; }
.item--profile.item--active { background: var(--color-surface); }
</style>
