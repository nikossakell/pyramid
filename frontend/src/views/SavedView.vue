<script setup lang="ts">
// S11 Αποθηκεύτηκε (ΚΡΑΤΑ): «Καταγράφηκε!», «Το μεσημεριανό σου είχε όσπρια.» [*πρότυπο] από τα food_groups του
// /meals/confirm (ή από το πρόχειρο όταν μπήκε στην ουρά). Η κάρτα δεν απονέμεται εδώ. «Θέλεις να μάθεις κάτι;» → Βοηθός.
import { computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import TopBar from '@/components/ui/TopBar.vue'
import AppButton from '@/components/ui/AppButton.vue'
import Icon from '@/components/ui/Icon.vue'
import { slotLabel, type MealSlot } from '@/api/meals'
import { useLogStore } from '@/stores/log'
import { useMealsStore } from '@/stores/meals'

const route = useRoute()
const router = useRouter()
const log = useLogStore()
const meals = useMealsStore()

const slot = computed(() => (route.query.slot as MealSlot) ?? 'lunch')
const queued = computed(() => route.query.queued === '1')
const codes = computed(() => String(route.query.groups ?? '').split(',').filter(Boolean))
const groups = computed(() => meals.shownGroups.filter((g) => codes.value.includes(g.code)))
const sentence = computed(() => {
  const l = groups.value.map((g) => g.label_el.toLowerCase())
  const s = slotLabel(slot.value).toLowerCase()
  if (!l.length) return `Το ${s} σου καταγράφηκε.`
  if (l.length === 1) return `Το ${s} σου είχε ${l[0]}.`
  return `Το ${s} σου είχε ${l.slice(0, -1).join(', ')} και ${l[l.length - 1]}.`
})

onMounted(() => log.start())        // το πρόχειρο τελείωσε· η εικόνα και το κείμενο ξεχνιούνται
</script>

<template>
  <div class="screen">
    <TopBar :avatar="false" />
    <main class="screen__body body">
      <span class="ok"><Icon name="check" :size="48" :stroke="3" /></span>
      <h2 class="t-display big" role="status">Καταγράφηκε!</h2>
      <p class="lead">{{ sentence }} <span class="muted t-caption">[*πρότυπο]</span></p>
      <p v-if="queued" class="t-label muted">Θα σταλεί μόλις συνδεθείς ξανά.</p>
      <ul v-if="groups.length" class="groups" aria-label="Ομάδες τροφίμων σε αυτό το γεύμα">
        <li v-for="g in groups" :key="g.code" class="g">
          <span class="gico"><Icon :name="g.code" :size="26" :stroke="1.9" /></span>
          <span class="t-caption glbl">{{ g.label_el }}</span>
        </li>
      </ul>
    </main>
    <footer class="screen__footer">
      <AppButton variant="secondary" icon="chat" @click="router.replace({ name: 'chat' })">Θέλεις να μάθεις κάτι για αυτό το γεύμα;</AppButton>
      <AppButton @click="router.replace({ name: 'today' })">Τέλος</AppButton>
    </footer>
  </div>
</template>

<style scoped>
.body { align-items: center; text-align: center; gap: 20px; padding: 24px 20px; justify-content: center; }
.ok { width: 96px; height: 96px; border-radius: 999px; background: var(--color-positive); color: #fff; display: flex; align-items: center; justify-content: center; }
.big { font-size: calc(34px * var(--text-scale)); }
.lead { font-size: calc(18px * var(--text-scale)); line-height: 1.45; }
.groups { display: flex; flex-wrap: wrap; justify-content: center; gap: 14px; }
.g { display: flex; flex-direction: column; align-items: center; gap: 5px; width: 72px; }
.gico { width: 52px; height: 52px; border-radius: 16px; background: var(--color-positive); color: #fff; display: flex; align-items: center; justify-content: center; }
.glbl { font-weight: 600; }
</style>
