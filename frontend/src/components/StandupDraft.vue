<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import ReportActions from './ReportActions.vue'
import WeekStrip from './WeekStrip.vue'
import { formatLine, rowsFromProjects, rowsFromReport } from '../composables/useDayEntry'
import { groupRows } from '../composables/useCategories'
import '../styles/daily.css'

const props = defineProps({ reports: { type: Array, required: true }, active: Boolean, reportError: Boolean, request: Object })
const emit = defineEmits(['saved', 'deleted'])
const dateParts = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/Athens', year: 'numeric', month: '2-digit', day: '2-digit',
}).formatToParts()
const today = ['year', 'month', 'day'].map(key => dateParts.find(part => part.type === key).value).join('-')
const day = ref(today)
const rows = ref([])
const next = ref('')
const blockers = ref('')
const saved = ref('')          // serialized state last loaded or saved, to detect edits
const draft = ref(null)        // live collection for the day: evidence, version and the suggestion
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const message = ref('')
const scheduledDates = ref([])
const scheduleUnavailable = ref(false)
let schedulePoll
let loadToken = 0

const lines = text => text.split('\n').map(line => line.trim()).filter(Boolean)
const approvedDates = computed(() => props.reports.map(report => report.date))
const pendingDates = computed(() => scheduledDates.value.filter(date => !approvedDates.value.includes(date)))
const report = computed(() => props.reports.find(item => item.date === day.value))
const serialize = () => JSON.stringify([rows.value.map(formatLine), lines(next.value), lines(blockers.value)])
const dirty = computed(() => serialize() !== saved.value)
const cleanRows = computed(() => rows.value.filter(row => row.text.trim()))
const canSave = computed(() => cleanRows.value.length > 0 && !saving.value && !loading.value && (dirty.value || !report.value))
const dayLabel = computed(() => new Intl.DateTimeFormat('el-GR', {
  weekday: 'long', day: 'numeric', month: 'long', timeZone: 'UTC',
}).format(new Date(day.value + 'T00:00:00Z')))
const state = computed(() => report.value ? (dirty.value ? 'Μη αποθηκευμένες αλλαγές' : 'Αποθηκευμένο') : 'Προσχέδιο από commits')

// The commits can move on after the text was saved; offer the newer sentences without overwriting anything.
const suggestion = computed(() => {
  if (!draft.value) return []
  const current = new Set(rows.value.map(row => row.name + '\u0000' + row.text.trim()))
  return rowsFromProjects(draft.value.projects).filter(row => !current.has(row.name + '\u0000' + row.text.trim()))
})
const categories = computed(() => draft.value?.categories ?? knownCategories.value)
const knownCategories = ref({})
const groups = computed(() => groupRows(rows.value, categories.value))
const projectNames = computed(() => Object.keys(categories.value))
const evidence = name => draft.value?.projects.find(project => project.name === name)

function apply(report_, drafted) {
  rows.value = report_ ? rowsFromReport(report_) : rowsFromProjects(drafted?.projects ?? [])
  next.value = report_?.sections[1]?.items.join('\n') ?? ''
  blockers.value = report_?.sections[2]?.items.join('\n') ?? ''
  saved.value = serialize()
}

async function load(date) {
  const token = ++loadToken
  loading.value = true
  error.value = ''
  draft.value = null
  apply(props.reports.find(item => item.date === date), null)
  try {
    let result = null
    if (pendingDates.value.includes(date)) result = await fetch('/api/scheduled/draft?date=' + date)
    if (!result?.ok) result = await fetch('/api/draft?date=' + date)
    if (!result.ok) throw new Error()
    const data = await result.json()
    if (token !== loadToken) return
    draft.value = data
    knownCategories.value = data.categories ?? knownCategories.value
    if (!props.reports.some(item => item.date === date)) apply(null, data)
  } catch {
    if (token === loadToken) error.value = 'Η τοπική συλλογή δεν ολοκληρώθηκε. Μπορείς να γράψεις χειροκίνητα.'
  } finally {
    if (token === loadToken) loading.value = false
  }
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

async function selectDay(date) {
  if (saving.value || date === day.value && draft.value) return
  if (dirty.value && !window.confirm('Να αλλάξει η ημέρα χωρίς αποθήκευση των αλλαγών;')) return
  day.value = date
  message.value = ''
  await load(date)
}

watch(() => props.active, active => {
  clearInterval(schedulePoll)
  if (active) {
    void refreshScheduled()
    schedulePoll = setInterval(refreshScheduled, 60000)
    if (!draft.value && !loading.value) void load(day.value)
  }
}, { immediate: true })
watch(() => props.request, request => { if (request) void selectDay(request.date) })
onUnmounted(() => clearInterval(schedulePoll))

function addRow() { rows.value.push({ name: '', text: '' }) }
function removeRow(index) { rows.value.splice(index, 1) }
function useSuggestion(row) {
  const same = rows.value.find(item => item.name && item.name === row.name)
  if (same) same.text = row.text
  else rows.value.push({ ...row })
}
function useAllSuggestions() { suggestion.value.slice().forEach(useSuggestion) }
function move(index, offset) {
  const target = index + offset
  if (target < 0 || target >= rows.value.length) return
  rows.value.splice(target, 0, rows.value.splice(index, 1)[0])
}

async function save() {
  if (!canSave.value) return
  saving.value = true
  error.value = ''
  message.value = ''
  try {
    const result = await fetch('/api/reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: day.value, version: report.value?.version ?? draft.value?.version ?? null, approved: true,
        completed: cleanRows.value.map(formatLine), next: lines(next.value), blockers: lines(blockers.value),
      }),
    })
    if (result.status === 409) {
      error.value = 'Η αναφορά άλλαξε από άλλη συσκευή. Φόρτωσα την τρέχουσα έκδοση, έλεγξε και αποθήκευσε ξανά.'
      emit('saved')
      return
    }
    if (!result.ok) throw new Error()
    rows.value = cleanRows.value
    saved.value = serialize()
    message.value = 'Αποθηκεύτηκε.'
    emit('saved')
    void refreshScheduled()
    draft.value = { ...draft.value, version: undefined }
  } catch {
    error.value = 'Η αναφορά δεν αποθηκεύτηκε. Έλεγξε το κείμενο και δοκίμασε ξανά.'
  } finally {
    saving.value = false
  }
}

async function reportDeleted(date) {
  emit('deleted', date)
  if (date) {
    message.value = 'Η αναφορά διαγράφηκε.'
    await load(day.value)
  }
}
</script>

<template>
  <section class="dl" aria-labelledby="daily-title">
    <div class="section-head">
      <h2 id="daily-title" tabindex="-1">Daily stand-up</h2>
      <span class="timezone">Ώρα Αθήνας</span>
    </div>
    <WeekStrip :day="day" :today="today" :approved="approvedDates" :pending="pendingDates" :busy="saving"
               @select="selectDay" />
    <p v-if="scheduleUnavailable || reportError" class="notice" role="status">
      Ο συγχρονισμός διακόπηκε προσωρινά. Γίνεται νέα προσπάθεια αυτόματα.
    </p>
    <p v-if="error" class="notice" role="alert">{{ error }}</p>

    <div class="dl-layout">
      <section class="dl-card dl-editor" aria-labelledby="selected-day" :aria-busy="loading">
        <header class="dl-head">
          <div>
            <h3 id="selected-day">{{ dayLabel }}</h3>
            <span class="dl-chip" :class="{ 'dl-dirty': dirty, 'dl-ok': report && !dirty }">{{ loading ? 'Φόρτωση…' : state }}</span>
          </div>
          <div class="dl-actions">
            <v-btn color="primary" :disabled="!canSave" :loading="saving" @click="save">Αποθήκευση</v-btn>
          </div>
        </header>
        <p v-if="message" class="week-message" role="status">{{ message }}</p>

        <div class="dl-body">
        <datalist id="dl-projects"><option v-for="name in projectNames" :key="name" :value="name"></option></datalist>
        <section v-for="group in groups" :key="group.key" class="dl-group" :style="{ '--cat': group.color }">
         <h4 class="dl-group-title"><span aria-hidden="true"></span>{{ group.label }}<small>{{ group.sub }}</small></h4>
         <ol class="dl-rows">
          <li v-for="{ row, index } in group.items" :key="index" class="dl-row">
            <div class="dl-row-top">
              <input v-model.trim="row.name" class="dl-name" list="dl-projects" placeholder="Project" aria-label="Όνομα project" maxlength="80">
              <span class="dl-tools">
                <button type="button" aria-label="Μετακίνηση πάνω" :disabled="index === 0" @click="move(index, -1)">↑</button>
                <button type="button" aria-label="Μετακίνηση κάτω" :disabled="index === rows.length - 1" @click="move(index, 1)">↓</button>
                <button type="button" aria-label="Διαγραφή γραμμής" class="dl-remove" @click="removeRow(index)">✕</button>
              </span>
            </div>
            <textarea v-model="row.text" rows="2" placeholder="Τι πέτυχες; Μία πρόταση με το αποτέλεσμα."
                      aria-label="Κείμενο γραμμής" maxlength="560"></textarea>
            <details v-if="evidence(row.name)" class="dl-evidence">
              <summary>Στοιχεία Git · {{ evidence(row.name).commits.length }} commits</summary>
              <ul><li v-for="commit in evidence(row.name).commits" :key="commit.sha"><code>{{ commit.sha }}</code> {{ commit.subject }}</li></ul>
              <p class="muted">Branches: {{ evidence(row.name).branches.join(', ') || 'Μη διαθέσιμο' }}</p>
              <p v-if="evidence(row.name).pushes.length" class="muted">
                Ενδείξεις push: {{ evidence(row.name).pushes.map(push => push.time + ' ' + push.branch).join(' · ') }}
              </p>
              <p class="muted">{{ evidence(row.name).source }}</p>
            </details>
          </li>
         </ol>
        </section>
        <p v-if="!rows.length && !loading" class="muted dl-empty">Δεν βρέθηκε δραστηριότητα. Πρόσθεσε μια γραμμή χειροκίνητα.</p>
        <v-btn variant="text" class="quiet-button" @click="addRow">+ Προσθήκη γραμμής</v-btn>
        </div>

        <div class="dl-notes">
          <label>Επόμενα<textarea v-model="next" rows="2" placeholder="Προαιρετικό"></textarea></label>
          <label>Εμπόδια<textarea v-model="blockers" rows="2" placeholder="Προαιρετικό"></textarea></label>
        </div>
      </section>

      <aside class="dl-side">
        <section v-if="suggestion.length" class="dl-card dl-suggest" aria-labelledby="suggest-title">
          <h3 id="suggest-title">Νεότερη πρόταση από commits</h3>
          <p class="muted">Δεν αλλάζει τίποτα μέχρι να την επιλέξεις και να αποθηκεύσεις.</p>
          <ul>
            <li v-for="row in suggestion" :key="row.name + row.text">
              <strong>{{ row.name }}</strong><p>{{ row.text }}</p>
              <v-btn size="small" variant="tonal" @click="useSuggestion(row)">Χρήση</v-btn>
            </li>
          </ul>
          <v-btn v-if="suggestion.length > 1" size="small" color="primary" variant="tonal" @click="useAllSuggestions">Χρήση όλων</v-btn>
        </section>
        <section class="dl-card">
          <h3>Συλλογή</h3>
          <p v-if="draft?.generatedAt" class="muted">
            Αυτόματο προσχέδιο · {{ new Date(draft.generatedAt).toLocaleString('el-GR', { timeZone: 'Europe/Athens' }) }}
          </p>
          <p v-else-if="draft" class="muted">Από τα τοπικά commits της ημέρας.</p>
          <p v-if="draft?.unavailable?.length" class="notice">Εκκρεμεί ο έλεγχος για {{ draft.unavailable.join(', ') }}.</p>
          <v-btn variant="tonal" size="small" :loading="loading" @click="load(day)">Επαναφόρτωση από commits</v-btn>
        </section>
        <section v-if="report" class="dl-card">
          <details class="draft-evidence">
            <summary>Ενέργειες αναφοράς</summary>
            <ReportActions :report="report" @deleted="reportDeleted" />
          </details>
        </section>
      </aside>
    </div>
  </section>
</template>
