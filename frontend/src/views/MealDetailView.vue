<script setup lang="ts">
// S12β Λεπτομέρεια γεύματος ως σελίδα (compact/medium· σε expanded το S12 τη δείχνει σε πάνελ δεξιά). Το περιεχόμενο και το
// M07 DeleteMeal είναι στο components/history/MealDetail.vue.
import { computed, onMounted, ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import AppButton from '@/components/ui/AppButton.vue'
import EmptyState from '@/components/ui/EmptyState.vue'
import MealDetail from '@/components/history/MealDetail.vue'
import { slotLabel } from '@/api/meals'
import { weekStart } from '@/lib/dates'
import { useMealsStore } from '@/stores/meals'

const route = useRoute()
const router = useRouter()
const meals = useMealsStore()

const id = computed(() => String(route.params.id))
const meal = computed(() => meals.meals.find((m) => m.meal_id === id.value) ?? null)
const looked = ref(false)
const detail = ref<InstanceType<typeof MealDetail> | null>(null)

onMounted(async () => {
  if (!meal.value) { try { await meals.loadRange(weekStart(meals.today), meals.today) } catch { /* offline */ } }
  looked.value = true
})
</script>

<template>
  <div class="screen">
    <TopBar :title="meal ? slotLabel(meal.meal_slot) : ''" back back-to="/history" />
    <main class="screen__body body">
      <MealDetail v-if="meal" ref="detail" :meal="meal" @deleted="router.replace({ name: 'history' })">
        <template #actions><span /></template>
      </MealDetail>
      <EmptyState v-else-if="looked" icon="history" text="Δεν βρήκα αυτό το γεύμα." />
    </main>
    <footer v-if="meal" class="screen__footer">
      <AppButton variant="destructive" icon="trash" @click="detail?.openDelete()">Διαγραφή γεύματος</AppButton>
    </footer>
  </div>
</template>

<style scoped>
.body { gap: 14px; padding: 8px 16px 16px; }
@media (min-width: 1024px) { .body, .screen > footer { max-width: 720px; } }
</style>
