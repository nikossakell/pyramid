<script setup lang="ts">
// S18 Απόρρητο & AI (ΚΡΑΤΑ): πλήρης σελίδα με κύλιση. Μεταβλητές: D1 (φωτογραφία, κείμενο του mockups_delta §3),
// D8 {retention_copy} και D10 (κείμενο κινδύνου) μένουν placeholders μέχρι την απόφαση.
import { ref } from 'vue'
import TopBar from '@/components/ui/TopBar.vue'
import PyramidMark from '@/components/ui/PyramidMark.vue'
import Icon from '@/components/ui/Icon.vue'
import LeaveStudyInfo from '@/components/modals/LeaveStudyInfo.vue'
import { PRIVACY_PHOTO_APPROVAL, PRIVACY_PHOTO_COPY } from '@/lib/copy'

const leaveOpen = ref(false)
const SECTIONS = [{ id: 'keep', label: 'Τι κρατάμε' }, { id: 'photos', label: 'Φωτογραφίες' }, { id: 'retention', label: 'Πόσο τα κρατάμε' },
                  { id: 'ai', label: 'Ο βοηθός AI' }, { id: 'about', label: 'Σχετικά' }]
const AI_LINES = [
  'Είναι πρόγραμμα AI, όχι άνθρωπος.',
  'Μπορεί να κάνει λάθη.',
  'Δεν είναι γιατρός.',
  'Απαντά μόνο από εγκεκριμένες πηγές και σου δείχνει από πού.',
  'Τα μηνύματά σου δεν τα διαβάζει κανείς την ώρα που γράφεις.',
]
</script>

<template>
  <div class="screen">
    <TopBar title="Απόρρητο & AI" back :avatar="false" back-to="/profile" />
    <main class="screen__body body">
      <nav class="setnav" aria-label="Ενότητες">
        <a v-for="s in SECTIONS" :key="s.id" :href="`#${s.id}`" class="setlink">{{ s.label }}</a>
      </nav>
      <div class="content">
      <section id="keep" class="sec">
        <h2 class="t-heading">Τι κρατάμε</h2>
        <p class="t-body">Τα γεύματα που επιβεβαιώνεις, με έναν κωδικό και όχι με το όνομά σου.</p>
      </section>
      <section id="photos" class="sec">
        <h2 class="t-heading">Φωτογραφίες</h2>
        <div class="box"><span class="boxcopy">{{ PRIVACY_PHOTO_COPY }}</span><span class="t-caption muted">{{ PRIVACY_PHOTO_APPROVAL }}</span></div>
      </section>
      <section id="retention" class="sec">
        <h2 class="t-heading">Πόσο τα κρατάμε</h2>
        <div class="box"><span class="boxcopy">[*διάρκεια τήρησης, D8]</span><span class="t-caption muted">[*να οριστεί μία τιμή από την ομάδα]</span></div>
      </section>
      <section id="ai" class="sec">
        <h2 class="t-heading">Ο βοηθός AI</h2>
        <ul class="bullets"><li v-for="l in AI_LINES" :key="l">{{ l }}</li></ul>
        <div class="risk">
          <span class="t-label bold">Αν γράψεις κάτι που δείχνει κίνδυνο</span>
          <span class="t-label">[*εγκεκριμένο κείμενο από την Επιτροπή Ηθικής, D10]</span>
        </div>
      </section>
      <section id="about" class="sec about">
        <PyramidMark :height="36" wordmark :word-size="32" />
        <h2 class="t-heading">Σχετικά με το PYRAMID</h2>
        <p class="t-label">Privacy-preserving Youth-oriented Reward-based AI Monitoring of Intake and Diet</p>
        <p class="t-label">Πιλοτική ερευνητική μελέτη του Αριστοτελείου Πανεπιστημίου Θεσσαλονίκης και του Πανεπιστημίου Μακεδονίας.</p>
        <dl class="dl">
          <div><dt class="t-caption muted bold">Ερευνητική ομάδα</dt><dd class="t-label">[*στοιχεία επικοινωνίας]</dd></div>
          <div><dt class="t-caption muted bold">Υπεύθυνος Προστασίας Δεδομένων ΑΠΘ</dt><dd class="t-label"><a href="mailto:data.protection@auth.gr" class="mail">data.protection@auth.gr</a></dd></div>
        </dl>
      </section>
      <button type="button" class="leave pressable" @click="leaveOpen = true"><span>Πώς σταματάω τη συμμετοχή</span><Icon name="chevron" :size="18" /></button>
      </div>
    </main>
    <LeaveStudyInfo :open="leaveOpen" @close="leaveOpen = false" />
  </div>
</template>

<style scoped>
.body { gap: 22px; padding: 8px 20px 40px; }
.setnav { display: none; }
.content { display: contents; }
/* expanded: διάταξη ρυθμίσεων, αριστερά λίστα ενοτήτων, δεξιά περιεχόμενο έως 720 px */
@media (min-width: 1024px) {
  .body { display: grid; grid-template-columns: 240px minmax(0, 720px); gap: 32px; align-items: start; }
  .setnav { display: flex; flex-direction: column; gap: 4px; position: sticky; top: 16px; }
  .setlink { display: flex; align-items: center; min-height: 44px; padding: 0 12px; border-radius: 12px; text-decoration: none; font-weight: 600; font-size: calc(15px * var(--text-scale)); color: var(--color-text-muted); }
  .setlink:hover { background: var(--color-surface); color: var(--color-text); }
  .content { display: flex; flex-direction: column; gap: 22px; min-width: 0; }
  .sec { scroll-margin-top: 16px; }
}
.sec { display: flex; flex-direction: column; gap: 8px; }
.box { border: 1.5px dashed var(--color-ink); border-radius: 12px; padding: 10px 12px; display: flex; flex-direction: column; gap: 4px; }
.boxcopy { font-weight: 700; font-size: calc(15px * var(--text-scale)); line-height: 1.4; }
.bullets { list-style: disc; padding-left: 20px; display: flex; flex-direction: column; gap: 8px; font-size: calc(16px * var(--text-scale)); line-height: 1.45; }
.risk { background: var(--color-surface); border-radius: 14px; padding: 12px 14px; display: flex; flex-direction: column; gap: 4px; }
.bold { font-weight: 700; }
.about { gap: 10px; }
.dl { display: flex; flex-direction: column; gap: 10px; margin: 0; }
.dl dd { margin: 0; }
.mail { font-weight: 600; }
.leave { display: flex; align-items: center; justify-content: space-between; min-height: 52px; border: 1px solid var(--color-line); border-radius: 16px; background: var(--color-bg); color: inherit; padding: 0 14px; font-weight: 600; font-size: calc(15px * var(--text-scale)); }
</style>
