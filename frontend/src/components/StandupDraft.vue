<script setup>
import { computed, onUnmounted, ref, toRef, watch } from 'vue'
import ReportActions from './ReportActions.vue'
import WeekExport from './WeekExport.vue'
import { formatLine, rowsFromProjects, rowsFromReport } from '../composables/useDayEntry'
import { groupRows } from '../composables/useCategories'
import { STATUS_LABELS, athensDay, previousWorkday, useWeek } from '../composables/useWeek'
import '../styles/week.css'
import '../styles/daily.css'

const props = defineProps({ reports: { type: Array, required: true }, active: Boolean, reportError: Boolean, request: Object })
const emit = defineEmits(['saved', 'deleted'])
const week = useWeek(toRef(props, 'active'), toRef(props, 'reports'))
const today = athensDay()
const weekend = [0, 6].includes(new Date(today + 'T00:00:00Z').getUTCDay())
const day = ref(weekend ? previousWorkday(today) : today)
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
const exporting = ref(false)
let schedulePoll
let loadToken = 0

const lines = text => text.split('\n').map(line => line.trim()).filter(Boolean)
const approvedDates = computed(() => props.reports.map(report => report.date))
const pendingDates = computed(() => scheduledDates.value.filter(date => !approvedDates.value.includes(date)))
const labels = STATUS_LABELS
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
  week.showWeekOf(date)
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

async function changeWeek(offset) {
  const index = week.days.value.findIndex(item => item.date === day.value)
  week.step(offset)
  const target = week.days.value[Math.max(index, 0)]
  if (target && target.status !== 'future') await selectDay(target.date)
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
  <section class="dl" aria-labelledby="week-title">
    <header class="wk-top">
      <h2 id="week-title" tabindex="-1">Εβδομάδα</h2>
      <div class="wk-kpis" aria-label="Σύνοψη εβδομάδας">
        <span class="wk-kpi" style="--tone:#62bdb0"><b>{{ week.summary.value.days }}/5</b> ημέρες με δουλειά</span>
        <span class="wk-kpi" style="--tone:#a396d6"><b>{{ week.summary.value.projects }}</b> projects</span>
        <span class="wk-kpi" style="--tone:#7cc79a"><b>{{ week.summary.value.saved }}/5</b> αποθηκευμένα</span>
      </div>
      <div class="wk-nav">
        <button class="wk-step" type="button" aria-label="Προηγούμενη εβδομάδα" :disabled="saving" @click="changeWeek(-1)">‹</button>
        <strong>{{ week.range.value }}</strong>
        <button class="wk-step" type="button" aria-label="Επόμενη εβδομάδα" :disabled="saving || !week.canGoForward.value" @click="changeWeek(1)">›</button>
        <v-btn variant="tonal" @click="exporting = true">Εξαγωγή εβδομάδας</v-btn>
      </div>
    </header>
    <p v-if="scheduleUnavailable || reportError || week.failed.value" class="notice" role="status">
      Ο συγχρονισμός διακόπηκε προσωρινά. Γίνεται νέα προσπάθεια αυτόματα.
    </p>
    <p v-if="error" class="notice" role="alert">{{ error }}</p>

    <div class="dl-layout">
      <nav class="wk-list" aria-label="Ημέρες της εβδομάδας">
        <button v-for="item in week.days.value" :key="item.date" type="button" class="wk-item"
                :class="['wk-' + item.status, { 'wk-selected': item.date === day, 'wk-today': item.today }]"
                :disabled="item.status === 'future' || saving" :aria-current="item.date === day ? 'date' : undefined"
                @click="selectDay(item.date)">
          <span class="wk-item-head">
            <b>{{ item.weekday }} <small>{{ item.date.slice(8) }}/{{ item.date.slice(5, 7) }}</small></b>
            <span v-if="labels[item.status]" class="wk-chip">{{ labels[item.status] }}</span>
          </span>
          <span class="wk-item-text">{{ item.rows.length ? item.rows.map(row => row.text).join(' · ') : item.status === 'future' ? '' : 'Χωρίς δραστηριότητα' }}</span>
        </button>
      </nav>

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

        <section v-if="suggestion.length" class="dl-suggest" aria-labelledby="suggest-title">
          <div class="dl-suggest-head">
            <h4 id="suggest-title">Νεότερη πρόταση από commits</h4>
            <v-btn v-if="suggestion.length > 1" size="small" color="primary" variant="tonal" @click="useAllSuggestions">Χρήση όλων</v-btn>
          </div>
          <ul>
            <li v-for="row in suggestion" :key="row.name + row.text">
              <span><strong>{{ row.name }}</strong> {{ row.text }}</span>
              <v-btn size="small" variant="tonal" @click="useSuggestion(row)">Χρήση</v-btn>
            </li>
          </ul>
        </section>

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

        <details class="dl-notes-wrap" :open="!!(next || blockers)">
          <summary>Επόμενα, εμπόδια και ενέργειες</summary>
          <div class="dl-notes">
            <label>Επόμενα<textarea v-model="next" rows="2" placeholder="Προαιρετικό"></textarea></label>
            <label>Εμπόδια<textarea v-model="blockers" rows="2" placeholder="Προαιρετικό"></textarea></label>
          </div>
          <div class="dl-more">
            <v-btn variant="tonal" size="small" :loading="loading" @click="load(day)">Επαναφόρτωση από commits</v-btn>
            <ReportActions v-if="report" :report="report" @deleted="reportDeleted" />
          </div>
        </details>
      </section>
    </div>

    <WeekExport v-model="exporting" :reports="reports" />
  </section>
</template>
