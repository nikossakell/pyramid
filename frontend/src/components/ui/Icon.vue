<script setup lang="ts">
// Εικονίδια γραμμής 24×24 (stroke currentColor), όπως στα mockups. Μόνο αυτά που χρειάζονται οι οθόνες.
const PATHS: Record<string, string> = {
  plus: 'M12 5v14M5 12h14',
  check: 'M5 12.5l4.5 4.5L19 7',
  x: 'M6 6l12 12M18 6L6 18',
  back: 'M15 5l-7 7 7 7',
  chevron: 'M9 5l7 7-7 7',
  camera: 'M4 8h3l2-3h6l2 3h3v11H4z M12 17a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z',
  pencil: 'M4 20l4-1 11-11-3-3L5 16z M14 6l3 3',
  search: 'M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14z M20 20l-4-4',
  home: 'M4 11l8-7 8 7v9H4z',
  history: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 7v5l3 2',
  chat: 'M4 5h16v11H9l-5 4z',
  cards: 'M6 4h9v14H6z M15 7l3 1-3 11-6-2',
  user: 'M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8z M4 21a8 8 0 0 1 16 0',
  help: 'M12 21s-7-4.5-7-10a4 4 0 0 1 7-2.5A4 4 0 0 1 19 11c0 5.5-7 10-7 10z',
  lock: 'M6 11h12v9H6z M8 11V8a4 4 0 0 1 8 0v3',
  offline: 'M3 3l18 18 M5 10a12 12 0 0 1 4-2.5 M9 14a6 6 0 0 1 2-1.2 M15 10l4-1 M12 18h.01',
  warning: 'M12 4l9 16H3z M12 10v4 M12 17h.01',
  clock: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 7v5l3 2',
  trash: 'M5 7h14 M9 7V4h6v3 M7 7l1 13h8l1-13',
  phone: 'M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A15 15 0 0 1 3 6a2 2 0 0 1 2-2z',
  info: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18z M12 11v5 M12 8h.01',
  sparkle: 'M12 3l2 6 6 2-6 2-2 6-2-6-6-2 6-2z',
  text: 'M5 6h14 M5 12h14 M5 18h9',
  mail: 'M4 6h16v12H4z M4 6l8 7 8-7',
  shield: 'M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6z',
  leaf: 'M5 19c0-8 5-13 14-14 0 9-5 14-14 14z M5 19l7-7',
  exit: 'M10 4H5v16h5 M14 8l4 4-4 4 M18 12H9',
  refresh: 'M20 12a8 8 0 1 1-2.3-5.7 M20 4v5h-5',
  dot: 'M12 12h.01',
  card: 'M7 3h10a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z M9 8h6 M9 12h6',
  // Ομάδες τροφίμων (C12): ένα απλό σύμβολο ανά κωδικό του /food-groups
  vegetables: 'M12 21c-4 0-7-3-7-7 0-3 2-5 4-6l3-4 3 4c2 1 4 3 4 6 0 4-3 7-7 7z M12 4v6',
  fruit: 'M12 7c-4-2-8 1-8 6 0 4 3 8 5 8 1 0 2-1 3-1s2 1 3 1c2 0 5-4 5-8 0-5-4-8-8-6z M12 7V4',
  legumes: 'M4 14c0-5 4-9 9-9h7c0 5-4 9-9 9H4z M8 11h.01 M12 10h.01 M16 9h.01',
  whole_grains: 'M12 21V9 M12 9c-3 0-5-2-5-5 3 0 5 2 5 5z M12 9c3 0 5-2 5-5-3 0-5 2-5 5z M12 14c-3 0-5-2-5-5 3 0 5 2 5 5z M12 14c3 0 5-2 5-5-3 0-5 2-5 5z',
  dairy: 'M9 3h6v3l2 4v11H7V10l2-4z M7 13h10',
  fish: 'M3 12c3-4 7-6 11-6 3 0 5 2 7 6-2 4-4 6-7 6-4 0-8-2-11-6z M3 12l4-4 M3 12l4 4 M17 11h.01',
  nuts: 'M12 3c5 0 8 4 8 9s-3 9-8 9-8-4-8-9 3-9 8-9z M12 3v18 M6 7c2 2 10 2 12 0',
  meat: 'M15 4a6 6 0 0 1 0 12l-4 4-3-3 4-4a6 6 0 0 1 3-9z M14 9h.01',
  eggs: 'M12 3c4 0 7 6 7 11a7 7 0 0 1-14 0c0-5 3-11 7-11z',
}
withDefaults(defineProps<{ name: string; size?: number; stroke?: number }>(), { size: 20, stroke: 2 })
</script>

<template>
  <svg :width="size" :height="size" viewBox="0 0 24 24" fill="none" stroke="currentColor" :stroke-width="stroke"
       stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path :d="PATHS[name] ?? PATHS.dot" />
  </svg>
</template>
