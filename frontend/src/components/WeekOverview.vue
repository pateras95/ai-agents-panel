<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import { rowsFromProjects, rowsFromReport } from '../composables/useDayEntry'
import { groupRows } from '../composables/useCategories'
import '../styles/week.css'

const props = defineProps({ active: Boolean, reports: Array })
const emit = defineEmits(['standup'])
function athensDay() {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Athens',
    year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts()
  return ['year', 'month', 'day'].map(key => parts.find(part => part.type === key).value).join('-')
}
const parse = date => new Date(date + 'T00:00:00Z')
function shift(date, days) {
  const value = parse(date)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}
const today = ref(athensDay())
const monday = ref(shift(today.value, -((parse(today.value).getUTCDay() + 6) % 7)))
const data = ref({})
const categories = ref({})
const dialog = ref(false)
const openDate = ref('')
const openedDay = computed(() => days.value.find(day => day.date === openDate.value))
function openDay(day) {
  if (day.status === 'future') return
  openDate.value = day.date
  dialog.value = true
}
const loading = ref(false)
const failed = ref(false)
let request
let interval

const names = new Intl.DateTimeFormat('el-GR', { weekday: 'long', timeZone: 'UTC' })
const dates = new Intl.DateTimeFormat('el-GR', { day: 'numeric', month: 'long', timeZone: 'UTC' })
const range = computed(() => `${dates.format(parse(monday.value))} – ${dates.format(parse(shift(monday.value, 4)))}`)
const canGoForward = computed(() => shift(monday.value, 7) <= today.value)

// The entry of a day is the saved report when there is one, otherwise the live draft from the commits.
const days = computed(() => Array.from({ length: 5 }, (_, index) => {
  const date = shift(monday.value, index)
  const live = data.value[date]
  const report = props.reports.find(item => item.date === date)
  const liveRows = rowsFromProjects(live?.projects ?? [])
  const rows = report ? rowsFromReport(report) : liveRows
  const savedNames = new Set(rows.map(row => row.name))
  const fresh = report && liveRows.some(row => !savedNames.has(row.name))
  const status = report ? (fresh ? 'update' : 'saved') : rows.length ? 'draft' : date > today.value ? 'future' : 'empty'
  return {
    date, status, rows, live, report, groups: groupRows(rows, categories.value),
    weekday: names.format(parse(date)), label: dates.format(parse(date)), today: date === today.value,
    notes: report ? report.sections.slice(1).filter(section => section.items.length) : [],
  }
}))
const labels = {
  saved: 'Αποθηκευμένο', draft: 'Προσχέδιο από commits', update: 'Νέα δραστηριότητα',
  empty: 'Χωρίς δραστηριότητα', future: '',
}
const summary = computed(() => {
  const worked = days.value.filter(day => day.rows.length)
  return { days: worked.length, projects: new Set(worked.flatMap(day => day.rows.map(row => row.name))).size,
    saved: days.value.filter(day => day.report).length }
})

async function refresh() {
  request?.abort()
  const controller = new AbortController()
  request = controller
  const week = monday.value
  today.value = athensDay()
  loading.value = true
  failed.value = false
  const timeout = setTimeout(() => controller.abort(), 15000)
  try {
    const response = await fetch('/api/week?start=' + week, { cache: 'no-store', signal: controller.signal })
    if (!response.ok) throw new Error()
    const { days: list } = await response.json()
    if (request === controller) {
      data.value = Object.fromEntries(list.map(item => [item.date, item]))
      categories.value = list.find(item => item.categories)?.categories ?? categories.value
    }
  } catch {
    if (request === controller) failed.value = true
  } finally {
    clearTimeout(timeout)
    if (request === controller) loading.value = false
  }
}
function step(offset) {
  monday.value = shift(monday.value, offset * 7)
  data.value = {}
  if (props.active) void refresh()
}
watch(() => props.active, active => {
  clearInterval(interval)
  if (active) {
    void refresh()
    interval = setInterval(refresh, 30000)
  } else {
    request?.abort()
  }
}, { immediate: true })
onUnmounted(() => { clearInterval(interval); request?.abort() })
</script>

<template>
  <section class="wk" aria-labelledby="week-title">
    <header class="wk-top">
      <h2 id="week-title" tabindex="-1">Εβδομάδα</h2>
      <div class="wk-kpis" aria-label="Σύνοψη εβδομάδας">
        <span class="wk-kpi" style="--tone:#62bdb0"><b>{{ summary.days }}/5</b> ημέρες με δουλειά</span>
        <span class="wk-kpi" style="--tone:#a396d6"><b>{{ summary.projects }}</b> projects</span>
        <span class="wk-kpi" style="--tone:#7cc79a"><b>{{ summary.saved }}/5</b> αποθηκευμένα</span>
      </div>
      <div class="wk-nav">
        <button class="wk-step" type="button" aria-label="Προηγούμενη εβδομάδα" @click="step(-1)">‹</button>
        <strong>{{ range }}</strong>
        <button class="wk-step" type="button" aria-label="Επόμενη εβδομάδα" :disabled="!canGoForward" @click="step(1)">›</button>
        <v-btn variant="tonal" :loading="loading" @click="refresh">Ανανέωση</v-btn>
      </div>
    </header>
    <p v-if="failed" class="notice" role="status">Η συλλογή δεν ήταν διαθέσιμη. Εμφανίζονται μόνο οι αποθηκευμένες αναφορές.</p>

    <div class="wk-board">
      <article v-for="day in days" :key="day.date" class="wk-day" :class="['wk-' + day.status, { 'wk-today': day.today }]"
               :role="day.status === 'future' ? undefined : 'button'" :tabindex="day.status === 'future' ? undefined : 0"
               :aria-label="day.status === 'future' ? undefined : `Άνοιγμα ${day.weekday} ${day.label}`"
               @click="openDay(day)" @keydown.enter.self="openDay(day)">
        <header>
          <span class="wk-weekday">{{ day.weekday }}</span>
          <b>{{ day.label }}</b>
          <span v-if="labels[day.status]" class="wk-chip">{{ labels[day.status] }}</span>
        </header>
        <div class="wk-body">
          <template v-if="day.rows.length">
            <section v-for="group in day.groups" :key="group.key" class="wk-group" :style="{ '--cat': group.color }">
              <h4><span aria-hidden="true"></span>{{ group.label }}</h4>
              <ul class="wk-lines">
                <li v-for="item in group.items" :key="item.index">
                  <strong v-if="item.row.name">{{ item.row.name }}</strong>
                  <p>{{ item.row.text }}</p>
                </li>
              </ul>
            </section>
          </template>
          <p v-else class="muted wk-none">{{ day.status === 'future' ? 'Δεν έχει έρθει ακόμα.' : loading ? 'Γίνεται έλεγχος…' : 'Δεν βρέθηκαν commits.' }}</p>
          <section v-for="note in day.notes" :key="note.label" class="wk-note">
            <small>{{ note.label }}</small>
            <p v-for="(item, index) in note.items" :key="index">{{ item }}</p>
          </section>
        </div>
        <v-btn v-if="day.status !== 'future'" class="wk-open" size="small" :variant="day.status === 'draft' || day.status === 'update' ? 'flat' : 'tonal'"
               :color="day.status === 'draft' || day.status === 'update' ? 'primary' : undefined"
               @click.stop="emit('standup', { date: day.date })">
          {{ day.report ? 'Επεξεργασία' : day.rows.length ? 'Αποθήκευση' : 'Καταχώριση' }}
        </v-btn>
      </article>
    </div>

    <v-dialog v-model="dialog" max-width="62rem" aria-labelledby="wk-dialog-title">
      <v-card v-if="openedDay" class="dialog-panel wk-dialog" :class="'wk-' + openedDay.status">
        <div class="dialog-heading">
          <div>
            <h2 id="wk-dialog-title">{{ openedDay.weekday }} {{ openedDay.label }}</h2>
            <span v-if="labels[openedDay.status]" class="wk-chip">{{ labels[openedDay.status] }}</span>
          </div>
          <v-btn variant="text" @click="dialog = false">Κλείσιμο</v-btn>
        </div>
        <div class="wk-dialog-body">
          <p v-if="!openedDay.rows.length" class="muted">{{ loading ? 'Γίνεται έλεγχος…' : 'Δεν βρέθηκαν commits για αυτή την ημέρα.' }}</p>
          <section v-for="group in openedDay.groups" :key="group.key" class="wk-group" :style="{ '--cat': group.color }">
            <h4><span aria-hidden="true"></span>{{ group.label }}<small>{{ group.sub }}</small></h4>
            <ul class="wk-lines">
              <li v-for="item in group.items" :key="item.index">
                <strong v-if="item.row.name">{{ item.row.name }}</strong>
                <p>{{ item.row.text }}</p>
              </li>
            </ul>
          </section>
          <section v-for="note in openedDay.notes" :key="note.label" class="wk-note">
            <small>{{ note.label }}</small>
            <p v-for="(item, index) in note.items" :key="index">{{ item }}</p>
          </section>
        </div>
        <div class="wk-dialog-actions">
          <v-btn color="primary" @click="dialog = false; emit('standup', { date: openedDay.date })">
            {{ openedDay.report ? 'Επεξεργασία στο Daily' : openedDay.rows.length ? 'Αποθήκευση στο Daily' : 'Καταχώριση στο Daily' }}
          </v-btn>
        </div>
      </v-card>
    </v-dialog>
  </section>
</template>
