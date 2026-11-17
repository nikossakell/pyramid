<script setup lang="ts">
// S12β Λεπτομέρεια γεύματος: τρόφιμα με μερίδα ως λέξη, πρόταση ομάδων, χωρίς γραμμάρια. «Διόρθωσε» είναι ΑΠΟΦΑΣΗ
// και δεν υλοποιείται. M07 DeleteMeal → DELETE /meals/{id}· με ALLOW_MEAL_DELETE=false ο server απαντά 403 → μαύρο toast.
// Κοινό περιεχόμενο για τη σελίδα MealDetailView (compact/medium) και το πάνελ δεξιά του S12 (expanded).
import { computed, ref } from 'vue'
import AppButton from '@/components/ui/AppButton.vue'
import CenterDialog from '@/components/ui/CenterDialog.vue'
import { ApiError } from '@/api/client'
import { deleteMeal, PORTIONS, slotLabel, type Meal } from '@/api/meals'
import { weekdayName } from '@/lib/dates'
import { useMealsStore } from '@/stores/meals'
import { useUiStore } from '@/stores/ui'

const props = defineProps<{ meal: Meal; heading?: boolean }>()
const emit = defineEmits<{ deleted: [] }>()
const meals = useMealsStore()
const ui = useUiStore()

const confirmOpen = ref(false)
const deleting = ref(false)

const SOURCE = { camera: 'με φωτογραφία', text: 'με κείμενο', manual: 'με αναζήτηση' } as const
const portionLabel = (p: string) => PORTIONS.find((x) => x.value === p)?.label ?? p
const groups = computed(() => {
  const codes = new Set(props.meal.items.map((i) => i.food_group).filter(Boolean) as string[])
  return meals.shownGroups.filter((g) => codes.has(g.code)).map((g) => g.label_el.toLowerCase())
})
const sentence = computed(() => {
  const s = slotLabel(props.meal.meal_slot).toLowerCase()
  const l = groups.value
  if (!l.length) return ''
  return l.length === 1 ? `Το ${s} σου είχε ${l[0]}.` : `Το ${s} σου είχε ${l.slice(0, -1).join(', ')} και ${l[l.length - 1]}.`
})

function openDelete(): void { confirmOpen.value = true }
defineExpose({ openDelete })

async function doDelete(): Promise<void> {
  deleting.value = true
  const id = props.meal.meal_id
  try {
    await deleteMeal(id)
    meals.removeMeal(id)
    confirmOpen.value = false
    ui.toast('Το γεύμα διαγράφηκε.', 'success')
    emit('deleted')
  } catch (e) {
    confirmOpen.value = false
    if (e instanceof ApiError && e.status === 403 && e.detail === 'meal_delete_disabled') ui.toast('Η διαγραφή δεν είναι διαθέσιμη τώρα. Αν θες να αλλάξει κάτι, μίλα με την ομάδα.', 'error')
    else if (e instanceof ApiError && e.status === 404) { meals.removeMeal(id); emit('deleted') }
    else if (!(e instanceof ApiError && (e.status === 401 || e.status === 403))) ui.toast('Δεν έγινε. Δοκίμασε ξανά σε λίγο.', 'error')
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div class="detail">
    <h2 v-if="heading" class="t-title">{{ slotLabel(meal.meal_slot) }}</h2>
    <p class="t-body muted">{{ weekdayName(meal.eaten_on) }} · καταγράφηκε {{ SOURCE[meal.source] }}</p>
    <ul class="items">
      <li v-for="i in meal.items" :key="i.food_id" class="item">
        <span class="name">{{ i.name_el }}</span>
        <span class="t-label muted">{{ portionLabel(i.portion) }}</span>
      </li>
    </ul>
    <p v-if="sentence" class="t-body">{{ sentence }}</p>
    <p class="t-caption muted">Κάθε αλλαγή καταγράφεται στο audit log της μελέτης.</p>
    <slot name="actions">
      <AppButton variant="destructive" icon="trash" @click="confirmOpen = true">Διαγραφή γεύματος</AppButton>
    </slot>

    <CenterDialog :open="confirmOpen" labelled-by="m07-title" described-by="m07-desc">
      <h2 id="m07-title" class="t-title">Να διαγραφεί το {{ slotLabel(meal.meal_slot).toLowerCase() }};</h2>
      <p id="m07-desc" class="t-body">Θα φύγει από το ιστορικό σου.</p>
      <div class="two">
        <AppButton variant="secondary" @click="confirmOpen = false">Άκυρο</AppButton>
        <AppButton variant="destructive" :loading="deleting" @click="doDelete">Διαγραφή</AppButton>
      </div>
    </CenterDialog>
  </div>
</template>

<style scoped>
.detail { display: flex; flex-direction: column; gap: 14px; }
.items { border: 1px solid var(--color-line); border-radius: 18px; }
.item { display: flex; align-items: center; justify-content: space-between; gap: 12px; min-height: 56px; padding: 0 14px; border-bottom: 1px solid var(--color-line); }
.item:last-child { border-bottom: 0; }
.name { font-weight: 600; font-size: calc(16px * var(--text-scale)); }
.two { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
</style>
