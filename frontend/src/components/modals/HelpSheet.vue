<script setup lang="ts">
// M01 HelpSheet (ΚΡΙΣΙΜΟ): γραμμές βοήθειας, «Μίλα με έναν ενήλικα», επικοινωνία με την ομάδα. Ανοίγει από κάθε HelpButton.
// Οι περιγραφές των γραμμών είναι [*εγκεκριμένη περιγραφή] μέχρι την έγκριση.
import BottomSheet from '@/components/ui/BottomSheet.vue'
import Icon from '@/components/ui/Icon.vue'
import { useUiStore } from '@/stores/ui'

const ui = useUiStore()
const LINES = [
  { number: '112', description: '[*εγκεκριμένη περιγραφή]' },
  { number: '1056', description: '[*εγκεκριμένη περιγραφή]' },
  { number: '1018', description: '[*εγκεκριμένη περιγραφή]' },
  { number: '10306', description: '[*εγκεκριμένη περιγραφή]' },
]
const TEAM_CONTACT = '[*στοιχεία επικοινωνίας]'
</script>

<template>
  <BottomSheet :open="ui.helpOpen" tone="help" close-button labelled-by="help-title" @close="ui.helpOpen = false">
    <template #default>
      <h2 id="help-title" class="t-title title">Χρειάζεσαι βοήθεια;</h2>
      <ul class="lines">
        <li v-for="l in LINES" :key="l.number">
          <a :href="`tel:${l.number}`" class="line pressable">
            <span class="ico"><Icon name="phone" :size="20" /></span>
            <span class="txt">
              <span class="num">{{ l.number }}</span>
              <span class="desc">{{ l.description }}</span>
            </span>
          </a>
        </li>
      </ul>
      <div class="adult"><Icon name="user" :size="22" /><span>Μίλα με έναν ενήλικα που εμπιστεύεσαι</span></div>
      <p class="team"><span>Επικοινωνία με την ερευνητική ομάδα</span><Icon name="chevron" :size="18" /><span class="visually-hidden">{{ TEAM_CONTACT }}</span></p>
      <p class="muted t-caption">{{ TEAM_CONTACT }}</p>
    </template>
  </BottomSheet>
</template>

<style scoped>
.title { margin-top: -44px; padding-right: 56px; font-size: calc(28px * var(--text-scale)); }
.lines { display: flex; flex-direction: column; gap: 8px; }
.line { display: flex; align-items: center; gap: 12px; background: #fff; color: #000; border: 2px solid #000; border-radius: 16px; padding: 6px 12px; min-height: 56px; text-decoration: none; }
.ico { width: 40px; height: 40px; border-radius: 999px; background: var(--color-help); display: flex; align-items: center; justify-content: center; flex: none; }
.txt { display: flex; flex-direction: column; }
.num { font-size: calc(20px * var(--text-scale)); font-weight: 700; }
.desc { font-size: calc(13px * var(--text-scale)); color: #5e5953; }
.adult { background: #fff; color: #000; border-radius: 16px; padding: 12px 14px; display: flex; align-items: center; gap: 12px; font-weight: 600; font-size: calc(15px * var(--text-scale)); }
.team { display: flex; align-items: center; justify-content: space-between; padding: 0 4px; font-weight: 600; font-size: calc(15px * var(--text-scale)); color: #000; }
</style>
