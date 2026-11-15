<script setup lang="ts">
// Chip «Μεσημεριανό ▾» (S08, S09): ανοίγει sheet με τα chips θέσεων.
import { ref } from 'vue'
import BottomSheet from '@/components/ui/BottomSheet.vue'
import Icon from '@/components/ui/Icon.vue'
import SlotChips from './SlotChips.vue'
import { slotLabel, type MealSlot } from '@/api/meals'

defineProps<{ modelValue: MealSlot }>()
const emit = defineEmits<{ 'update:modelValue': [v: MealSlot] }>()
const open = ref(false)
function pick(v: MealSlot): void { emit('update:modelValue', v); open.value = false }
</script>

<template>
  <button type="button" class="chip chip--outline slotbtn" aria-haspopup="dialog" @click="open = true">
    {{ slotLabel(modelValue) }}<Icon name="chevron" :size="16" class="down" />
  </button>
  <BottomSheet :open="open" title="Ποιο γεύμα;" @close="open = false">
    <SlotChips :model-value="modelValue" @update:model-value="pick" />
  </BottomSheet>
</template>

<style scoped>
.slotbtn { align-self: flex-start; border-color: var(--color-ink); }
.down { transform: rotate(90deg); }
</style>
