<script setup lang="ts">
// C13 WeekDots (ΚΡΑΤΑ): Δευτέρα–Κυριακή. Γεμάτη = τουλάχιστον 2 καταγραφές (από το /meals), κενή ουδέτερη,
// σήμερα = μαύρο δαχτυλίδι, μελλοντική = διακεκομμένη. Χωρίς μετρητή σερί, χωρίς αριθμούς.
import { computed } from 'vue'
import Icon from '@/components/ui/Icon.vue'
import { addDays, WEEKDAY_LETTERS, WEEKDAY_NAMES, weekStart } from '@/lib/dates'
import type { Meal } from '@/api/meals'

const props = defineProps<{ meals: Meal[]; today: string }>()

const days = computed(() => {
  const start = weekStart(props.today)
  return WEEKDAY_LETTERS.map((letter, i) => {
    const iso = addDays(start, i)
    const count = props.meals.filter((m) => m.eaten_on === iso).length
    const isToday = iso === props.today
    const future = iso > props.today
    const full = count >= 2
    const state = future ? 'μελλοντική' : full ? 'γεμάτη' : 'κενή'
    return { iso, letter, isToday, future, full, label: `${WEEKDAY_NAMES[i]}${isToday ? ', σήμερα' : ''}, ${state}` }
  })
})
</script>

<template>
  <section class="card box">
    <h2 class="t-caption head">Αυτή την εβδομάδα</h2>
    <ol aria-label="Ημέρες με τουλάχιστον δύο καταγραφές" class="row">
      <li v-for="d in days" :key="d.iso" class="day">
        <span class="dot" :class="{ 'dot--full': d.full, 'dot--today': d.isToday && !d.full, 'dot--future': d.future }" :aria-label="d.label">
          <Icon v-if="d.full" name="check" :size="16" :stroke="3" />
        </span>
        <span class="letter" :class="{ 'letter--today': d.isToday }">{{ d.letter }}</span>
      </li>
    </ol>
  </section>
</template>

<style scoped>
.box { border-radius: 20px; padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.head { font-weight: 700; font-size: calc(15px * var(--text-scale)); }
.row { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 4px; }
.day { display: flex; flex-direction: column; align-items: center; gap: 4px; }
.dot { width: 32px; height: 32px; border-radius: 999px; border: 1.5px solid var(--color-absent); display: flex; align-items: center; justify-content: center; color: #000; }
.dot--full { background: var(--color-primary); border: 0; }
.dot--today { border: 2.5px solid var(--color-ink); }
.dot--future { border: 1.5px dashed var(--color-line); }
.letter { font-size: calc(13px * var(--text-scale)); color: var(--color-text-muted); }
.letter--today { color: var(--color-text); font-weight: 700; }
</style>
