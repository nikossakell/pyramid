<script setup lang="ts">
// S08 Επιβεβαίωση και διόρθωση (ΚΡΑΤΑ · ΚΡΙΣΙΜΗ): R5 τίποτα δεν αποθηκεύεται χωρίς «Σωστό, αποθήκευσε». Χωρίς γραμμάρια.
// Μερίδα χωρίς προεπιλογή (mockups_delta §5). Γραμμή χωρίς αντιστοίχιση: εναλλακτικές ή αναζήτηση. Έως 10 τρόφιμα.
// POST /meals/confirm με client_meal_id (idempotent) και analysis_id (αν προήλθε από πρόταση). Εκτός σύνδεσης: μόνο
// καταγραφή από αναζήτηση (source=manual) μπαίνει στην ουρά· οι άλλες μένουν εδώ με ήπιο μήνυμα.
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'
import SlotPicker from '@/components/log/SlotPicker.vue'
import FoodItemRow from '@/components/log/FoodItemRow.vue'
import PortionPicker from '@/components/modals/PortionPicker.vue'
import { ApiError, OFFLINE } from '@/api/client'
import { confirmMeal, type Portion } from '@/api/meals'
import { useLogStore } from '@/stores/log'
import { useMealsStore } from '@/stores/meals'
import { useQueueStore } from '@/stores/queue'
import { useUiStore } from '@/stores/ui'
import { useBreakpoint } from '@/composables/useBreakpoint'

const router = useRouter()
const log = useLogStore()
const meals = useMealsStore()
const queue = useQueueStore()
const ui = useUiStore()
const { isExpanded } = useBreakpoint()

const saving = ref(false)
const pickerKey = ref<number | null>(null)
const pickerItem = computed(() => log.items.find((i) => i.key === pickerKey.value) ?? null)

const hint = computed(() => {
  if (log.active.length === 0) return 'Πρόσθεσε τουλάχιστον ένα φαγητό για να αποθηκευτεί'
  if (log.unresolved.length) return `Διάλεξε ή αφαίρεσε το «${log.unresolved[0].name_el}» για να αποθηκευτεί`
  if (log.withoutPortion.length) return `Διάλεξε μερίδα για το ${log.withoutPortion[0].name_el.toLowerCase()}`
  return ''
})

function groupsOf(): string[] {
  const set = new Set<string>()
  for (const i of log.active) if (i.food_group) set.add(i.food_group)
  return meals.shownGroups.filter((g) => set.has(g.code)).map((g) => g.code)
}

async function save(): Promise<void> {
  if (!log.canSave || saving.value) return
  saving.value = true
  const body = log.body()
  try {
    const res = await confirmMeal(body)
    meals.loadToday().catch(() => {})
    router.replace({ name: 'saved', query: { slot: res.meal_slot, groups: res.food_groups.join(',') } })
  } catch (e) {
    if (e instanceof ApiError && e.status === OFFLINE && body.source === 'manual') {
      queue.enqueue({ body, names: log.active.map((i) => i.name_el), groups: groupsOf() })
      router.replace({ name: 'saved', query: { slot: body.meal_slot, groups: groupsOf().join(','), queued: '1' } })
    } else if (e instanceof ApiError && e.status === OFFLINE) {
      ui.toast('Δεν στάλθηκε. Έλεγξε τη σύνδεση και πάτα ξανά «Σωστό, αποθήκευσε».', 'error')
    } else if (e instanceof ApiError && e.status === 409) {
      ui.toast('Αυτή η καταγραφή δεν στάλθηκε. Γράψ’ τη ξανά.', 'error')
      cancel()
    } else if (!(e instanceof ApiError && (e.status === 401 || e.status === 403))) {
      ui.toast('Κάτι πήγε στραβά. Δοκίμασε ξανά σε λίγο.', 'error')
    }
  } finally {
    saving.value = false
  }
}

function cancel(): void {
  log.start()
  router.replace({ name: 'today' })
}
function setPortion(key: number, p: Portion): void { log.setPortion(key, p) }
</script>

<template>
  <div class="screen">
    <TopBar title="Επιβεβαίωση" back :avatar="false" back-to="/log" />
    <main class="screen__body body">
      <div class="list">
        <h2 class="t-title">Βρήκα αυτά. Είναι σωστά;</h2>
        <SlotPicker v-if="!isExpanded" v-model="log.slot" />

        <FoodItemRow v-for="it in log.items" :key="it.key" :item="it" :source="log.source"
                     @portion="setPortion(it.key, $event)" @remove="log.remove(it.key)" @restore="log.restore(it.key)"
                     @alternative="log.chooseAlternative(it.key, $event)" @search="router.push({ name: 'search', query: { from: 'confirm', replace: String(it.key) } })"
                     @ask-portion="pickerKey = it.key" />

        <button v-if="!log.isFull && !isExpanded" type="button" class="add pressable" @click="router.push({ name: 'search', query: { from: 'confirm' } })">
          <Icon name="plus" :size="20" />Πρόσθεσε κάτι που λείπει
        </button>
      </div>

      <!-- expanded: sticky πάνελ δεξιά με γεύμα, «+ Πρόσθεσε», «Σωστό, αποθήκευσε» και το «τι λείπει» (ίδιο περιεχόμενο με το footer) -->
      <aside v-if="isExpanded" class="side" aria-label="Αποθήκευση γεύματος">
        <div class="field">
          <span class="field__label">Γεύμα</span>
          <SlotPicker v-model="log.slot" />
        </div>
        <button v-if="!log.isFull" type="button" class="add pressable" @click="router.push({ name: 'search', query: { from: 'confirm' } })">
          <Icon name="plus" :size="20" />Πρόσθεσε κάτι που λείπει
        </button>
        <p v-if="hint" class="t-caption muted">{{ hint }}</p>
        <AppButton :disabled="!log.canSave" :loading="saving" @click="save">Σωστό, αποθήκευσε</AppButton>
        <AppButton variant="ghost" @click="cancel">Ακύρωση</AppButton>
      </aside>
    </main>
    <footer v-if="!isExpanded" class="screen__footer">
      <p v-if="hint" class="t-caption muted">{{ hint }}</p>
      <AppButton :disabled="!log.canSave" :loading="saving" @click="save">Σωστό, αποθήκευσε</AppButton>
      <AppButton variant="ghost" @click="cancel">Ακύρωση</AppButton>
    </footer>

    <PortionPicker :open="pickerItem !== null" :name="pickerItem?.name_el ?? ''" :model-value="pickerItem?.portion ?? null"
                   @update:model-value="pickerKey !== null && setPortion(pickerKey, $event)" @close="pickerKey = null" />
  </div>
</template>

<style scoped>
.body { gap: 12px; padding: 8px 16px 16px; }
.list { display: contents; }
/* expanded: αριστερά (8) οι γραμμές, δεξιά (4) sticky πάνελ */
@media (min-width: 1024px) {
  .body { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr)); gap: 24px; align-items: start; padding-bottom: 40px; }
  .list { display: flex; flex-direction: column; gap: 12px; grid-column: 1 / span 8; min-width: 0; }
  .side { grid-column: 9 / span 4; position: sticky; top: 16px; display: flex; flex-direction: column; gap: 12px; border: 1px solid var(--color-line); border-radius: 20px; padding: 18px 16px; box-shadow: var(--shadow-card); background: var(--color-bg); }
}
.add { height: 52px; border-radius: 16px; border: 1.5px dashed var(--color-absent); background: var(--color-bg); color: inherit; font-weight: 600; font-size: calc(15px * var(--text-scale)); display: inline-flex; align-items: center; justify-content: center; gap: 8px; }
</style>
