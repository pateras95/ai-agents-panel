<script setup>
import { computed, nextTick, onUnmounted, ref, watch } from 'vue'
import ReportActions from './ReportActions.vue'
import WeekStrip from './WeekStrip.vue'

const props = defineProps({ reports: { type: Array, required: true }, active: Boolean, reportError: Boolean, request: Object })
const emit = defineEmits(['saved', 'deleted'])
const dateParts = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/Athens', year: 'numeric', month: '2-digit', day: '2-digit',
}).formatToParts()
const today = ['year', 'month', 'day'].map(key => dateParts.find(part => part.type === key).value).join('-')
const day = ref(today)
const draft = ref(null)
const completed = ref('')
const next = ref('')
const blockers = ref('')
const editing = ref(false)
const confirming = ref(false)
const selectedProject = ref(0)
const detailsPanel = ref(null)
const busy = ref(false)
const error = ref('')
const message = ref('')
const scheduledDates = ref([])
const approvalHold = ref('')
const scheduleUnavailable = ref(false)
let schedulePoll

const lines = text => text.split('\n').map(line => line.trim()).filter(Boolean)
const approvedDates = computed(() => props.reports.map(report => report.date))
const pendingDates = computed(() => scheduledDates.value.filter(date =>
  date !== approvalHold.value && !approvedDates.value.includes(date)))
const report = computed(() => props.reports.find(item => item.date === day.value))
const canSave = computed(() => draft.value?.date === day.value && lines(completed.value).length > 0)
const displayedLines = computed(() => draft.value ? lines(completed.value) : (report.value?.sections[0]?.items ?? []))
const cards = computed(() => displayedLines.value.map(line => {
  const separator = line.indexOf(':')
  return separator > 0
    ? { name: line.slice(0, separator).trim(), summary: line.slice(separator + 1).trim() }
    : { name: 'Καταχώριση', summary: line }
}))
const projectEvidence = computed(() => {
  const card = cards.value[selectedProject.value]
  return card ? draft.value?.projects.find(project => project.name === card.name) : undefined
})
const dayLabel = computed(() => new Intl.DateTimeFormat('el-GR', {
  weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC',
}).format(new Date(day.value + 'T00:00:00Z')))

function reset() {
  draft.value = null
  completed.value = next.value = blockers.value = error.value = message.value = ''
  editing.value = confirming.value = false
  selectedProject.value = 0
}

async function refreshScheduled() {
  try {
    const response = await fetch('/api/scheduled', { cache: 'no-store' })
    if (!response.ok) throw new Error()
    scheduledDates.value = (await response.json()).dates
    scheduleUnavailable.value = false
  } catch {
    scheduleUnavailable.value = true
  }
}

watch(() => props.active, active => {
  clearInterval(schedulePoll)
  if (active) {
    void refreshScheduled()
    schedulePoll = setInterval(refreshScheduled, 60000)
  }
}, { immediate: true })
onUnmounted(() => clearInterval(schedulePoll))

async function selectDay(date) {
  if (busy.value) return
  if (day.value !== date) {
    const hasEdits = draft.value && (completed.value !== (
      draft.value?.projects.map(project => `${project.name}: ${project.summary}`).join('\n') ?? ''
    ) || next.value || blockers.value)
    if (hasEdits && !window.confirm('Να αλλάξει η ημέρα χωρίς αποθήκευση των αλλαγών;')) return
    day.value = date
    reset()
  }
  if (!draft.value && pendingDates.value.includes(date)) await generate(true)
}

async function showEvidence(index) {
  selectedProject.value = index
  await nextTick()
  if (window.matchMedia('(max-width: 66rem)').matches) {
    detailsPanel.value?.scrollIntoView({ block: 'nearest' })
  }
}

async function generate(scheduled = false) {
  if (busy.value) return
  reset()
  busy.value = true
  try {
    const endpoint = scheduled ? '/api/scheduled/draft?' : '/api/draft?'
    const result = await fetch(endpoint + new URLSearchParams({ date: day.value }))
    if (!result.ok) throw new Error()
    draft.value = await result.json()
    completed.value = draft.value.projects.map(project => `${project.name}: ${project.summary}`).join('\n')
    editing.value = !completed.value
  } catch {
    error.value = 'Η τοπική συλλογή δεν ολοκληρώθηκε. Δοκίμασε ξανά.'
  } finally {
    busy.value = false
  }
}

async function save() {
  if (!confirming.value || !canSave.value || busy.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await fetch('/api/reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: draft.value.date, version: draft.value.version, approved: true,
        completed: lines(completed.value), next: lines(next.value), blockers: lines(blockers.value),
      }),
    })
    if (result.status === 409) {
      error.value = 'Η αναφορά άλλαξε. Δημιούργησε νέο προσχέδιο πριν την αντικατάσταση.'
      return
    }
    if (!result.ok) throw new Error()
    approvalHold.value = day.value
    reset()
    message.value = 'Η εγκεκριμένη αναφορά αποθηκεύτηκε.'
    emit('saved')
    void refreshScheduled()
  } catch {
    error.value = 'Η αναφορά δεν αποθηκεύτηκε. Έλεγξε το κείμενο και δοκίμασε ξανά.'
  } finally {
    confirming.value = false
    busy.value = false
  }
}

watch(() => props.request, async request => {
  if (!request || busy.value) return
  await selectDay(request.date)
  if (request.generate && day.value === request.date && !draft.value) await generate()
})

function reportDeleted(date) {
  emit('deleted', date)
  if (date) message.value = 'Η αναφορά διαγράφηκε.'
}
</script>

<template>
  <section class="weekly-standup" aria-labelledby="daily-title">
    <div class="section-head">
      <h2 id="daily-title" tabindex="-1">Daily stand-up</h2>
      <span class="timezone">Ώρα Αθήνας</span>
    </div>
    <WeekStrip :day="day" :today="today" :approved="approvedDates" :pending="pendingDates" :busy="busy"
               @select="selectDay" />
    <div v-if="pendingDates.length" class="week-queue">
      <strong>Προς έγκριση</strong>
      <v-btn v-for="date in pendingDates" :key="date" color="primary" variant="tonal" :disabled="busy"
             @click="selectDay(date)">{{ date.split('-').reverse().join('/') }}</v-btn>
    </div>
    <p v-if="scheduleUnavailable || reportError" class="notice" role="status">
      Ο συγχρονισμός διακόπηκε προσωρινά. Γίνεται νέα προσπάθεια αυτόματα.
    </p>
    <p v-if="error" class="notice" role="alert">{{ error }}</p>
    <p v-if="message" class="week-message" role="status">{{ message }}</p>

    <div class="week-workspace">
      <section class="week-content" aria-labelledby="selected-day" :aria-busy="busy">
        <div class="week-content-heading">
          <div>
            <h3 id="selected-day">{{ dayLabel }}</h3>
            <p class="muted">
              {{ draft ? (draft.generatedAt ? 'Αυτόματο προσχέδιο' : 'Προσχέδιο') : report ? 'Εγκεκριμένη αναφορά' : 'Χωρίς αναφορά' }}
            </p>
          </div>
          <div v-if="!draft" class="week-actions">
            <v-btn v-if="pendingDates.includes(day)" color="primary" :loading="busy"
                   @click="generate(true)">Άνοιγμα προσχεδίου</v-btn>
            <v-btn v-else-if="!report" color="primary" :loading="busy" @click="generate()">Δημιουργία προσχεδίου</v-btn>
          </div>
        </div>

        <p v-if="!cards.length && !editing" class="week-empty muted">
          {{ draft ? 'Δεν βρέθηκε τεκμηριωμένη εργασία.' : 'Δεν υπάρχει καταχωρισμένο stand-up για αυτή την ημέρα.' }}
        </p>
        <div v-if="cards.length" class="project-grid">
          <article v-for="(card, index) in cards" :key="index" class="project-card"
                   :class="{ 'project-selected': draft && index === selectedProject }">
            <h4>{{ card.name }}</h4>
            <p>{{ card.summary }}</p>
            <button v-if="draft" type="button" class="project-link"
                    @click="showEvidence(index)">Στοιχεία project</button>
          </article>
        </div>

        <div v-if="draft" class="week-editor">
          <p v-if="draft.unavailable.length" class="notice">Εκκρεμεί ο έλεγχος για {{ draft.unavailable.join(', ') }}.</p>
          <div class="week-actions">
            <v-btn variant="tonal" :disabled="busy" @click="editing = !editing">
              {{ editing ? 'Κλείσιμο επεξεργασίας' : 'Επεξεργασία' }}
            </v-btn>
            <v-btn v-if="!confirming" color="primary" :disabled="!canSave || busy"
                   @click="confirming = true">Έγκριση αναφοράς</v-btn>
          </div>
          <div v-if="editing" class="draft-panel draft-editor">
            <label>Αποτέλεσμα · μία πρόταση ανά project
              <textarea v-model="completed" rows="5" :disabled="busy" @input="confirming = false"></textarea>
            </label>
            <details class="draft-evidence">
              <summary>Προαιρετικές σημειώσεις</summary>
              <label>Επόμενα<textarea v-model="next" rows="2" :disabled="busy" @input="confirming = false"></textarea></label>
              <label>Εμπόδια<textarea v-model="blockers" rows="2" :disabled="busy" @input="confirming = false"></textarea></label>
            </details>
          </div>
          <div v-if="confirming" class="approval" role="group" aria-label="Επιβεβαίωση αποθήκευσης">
            <p>{{ draft.version ? 'Να αντικατασταθεί η υπάρχουσα αναφορά αυτής της ημέρας;' : 'Να αποθηκευτεί το προσχέδιο ως εγκεκριμένη αναφορά;' }}</p>
            <v-btn color="primary" :loading="busy" @click="save">Επιβεβαίωση</v-btn>
            <v-btn variant="text" :disabled="busy" @click="confirming = false">Ακύρωση</v-btn>
          </div>
        </div>
        <template v-else-if="report">
          <section v-for="section in report.sections.slice(1).filter(section => section.items.length)" :key="section.label" class="week-notes">
            <h4>{{ section.label }}</h4>
            <ul><li v-for="(item, index) in section.items" :key="index">{{ item }}</li></ul>
          </section>
        </template>
      </section>

      <aside ref="detailsPanel" class="week-details" aria-labelledby="details-title">
        <h3 id="details-title">Λεπτομέρειες ημέρας</h3>
        <p v-if="draft?.generatedAt" class="muted">
          Συλλογή {{ new Date(draft.generatedAt).toLocaleString('el-GR', { timeZone: 'Europe/Athens' }) }}
        </p>
        <template v-if="draft">
          <div v-if="projectEvidence" class="evidence-project">
            <h4>{{ projectEvidence.name }}</h4>
            <p class="muted">{{ projectEvidence.source }}</p>
            <details class="draft-evidence">
              <summary>Πηγές Git</summary>
              <p>Τοπικά branches · {{ projectEvidence.branches.join(', ') || 'Μη διαθέσιμο' }}</p>
              <p>Ενδείξεις push</p>
              <ul v-if="projectEvidence.pushes.length">
                <li v-for="(push, index) in projectEvidence.pushes" :key="index">{{ push.time }} · {{ push.branch }} · {{ push.sha }}</li>
              </ul>
              <p v-else>Δεν βρέθηκαν.</p>
              <p>Commits</p>
              <ul v-if="projectEvidence.commits.length">
                <li v-for="commit in projectEvidence.commits" :key="commit.sha">{{ commit.sha }} · {{ commit.subject }}</li>
              </ul>
              <p v-else>Δεν βρέθηκαν.</p>
            </details>
          </div>
          <p v-else class="muted">Δεν υπάρχουν πηγές Git για την επιλεγμένη γραμμή.</p>
        </template>
        <template v-else-if="report">
          <details class="draft-evidence">
            <summary>Ενέργειες αναφοράς</summary>
            <v-btn variant="tonal" :loading="busy" @click="generate()">Νέο προσχέδιο</v-btn>
            <ReportActions :report="report" @deleted="reportDeleted" />
          </details>
        </template>
        <p v-else class="muted">Επίλεξε ημέρα με αναφορά ή δημιούργησε προσχέδιο.</p>
      </aside>
    </div>
  </section>
</template>
