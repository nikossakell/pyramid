<script setup lang="ts">
// C05 AccessKeyInput (ΚΡΑΤΑ): κενό / εστίαση / σφάλμα / κλειδωμένο. Το κλειδί δεν αποθηκεύεται πουθενά.
import Icon from './Icon.vue'
defineProps<{ modelValue: string; error?: string | null; locked?: boolean; lockedText?: string }>()
const emit = defineEmits<{ 'update:modelValue': [v: string] }>()
</script>

<template>
  <div class="field">
    <label class="field__label" for="access-key">Κλειδί πρόσβασης</label>
    <div class="wrap">
      <Icon v-if="locked" name="lock" :size="20" class="lockicon" />
      <input id="access-key" class="input" :class="{ 'input--error': !!error, 'input--locked': locked }" type="text" inputmode="text"
             autocomplete="off" autocapitalize="characters" spellcheck="false" :placeholder="locked ? 'Κλειδωμένο' : 'Γράψε το κλειδί σου'"
             :disabled="locked" :value="modelValue" :aria-invalid="!!error || undefined" :aria-describedby="error ? 'access-key-error' : undefined"
             @input="emit('update:modelValue', ($event.target as HTMLInputElement).value)" />
    </div>
    <div v-if="error" id="access-key-error" class="msg" role="alert"><Icon name="warning" :size="18" /><span>{{ error }}</span></div>
    <div v-if="locked && lockedText" class="msg" role="status">{{ lockedText }}</div>
  </div>
</template>

<style scoped>
.wrap { position: relative; }
.lockicon { position: absolute; left: 16px; top: 50%; transform: translateY(-50%); color: var(--color-text-muted); }
.input { letter-spacing: 1px; }
.input--locked { padding-left: 48px; }
.msg { display: flex; align-items: flex-start; gap: 8px; font-size: calc(15px * var(--text-scale)); line-height: 1.4; }
</style>
