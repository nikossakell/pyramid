<script setup lang="ts">
// logo.mark (placeholder: τα blobs του canvas δεν υπάρχουν) και logo.full «pyramid» σε display γραμματοσειρά.
withDefaults(defineProps<{ height?: number; wordmark?: boolean; wordSize?: number; inverse?: boolean }>(),
  { height: 48, wordmark: false, wordSize: 40, inverse: false })
</script>

<template>
  <span class="mark" :style="{ gap: wordmark ? '10px' : '0' }">
    <svg :height="height" :width="height * 0.75" viewBox="0 0 96 128" aria-hidden="true">
      <path d="M48 6 L92 122 H4 Z" :fill="inverse ? '#FFFFFF' : '#F14711'" />
      <path d="M48 46 L76 122 H20 Z" :fill="inverse ? '#121110' : '#FEB211'" />
      <path d="M48 86 L62 122 H34 Z" :fill="inverse ? '#FFFFFF' : '#B1318E'" />
    </svg>
    <span v-if="wordmark" class="word" :style="{ fontSize: wordSize + 'px' }">pyramid</span>
  </span>
</template>

<style scoped>
.mark { display: inline-flex; align-items: center; }
.word { font-family: var(--font-display); font-weight: 400; line-height: 1; letter-spacing: -0.5px; }
</style>
