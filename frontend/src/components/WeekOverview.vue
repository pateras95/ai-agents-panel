<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'
import WeekStrip from './WeekStrip.vue'

const props = defineProps({ active: Boolean, reports: Array })
const emit = defineEmits(['standup'])
function athensDay() {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Athens',
    year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts()
  return ['year', 'month', 'day'].map(key => parts.find(part => part.type === key).value).join('-')
}
const today = ref(athensDay())
const day = ref(today.value)
const data = ref({})
const pendingDates = ref([])
const loading = ref(false)
const failed = ref(false)
let request
let interval
const approved = computed(() => props.reports.map(report => report.date))
const pending = computed(() => pendingDates.value.filter(date => !approved.value.includes(date)))
const start = computed(() => {
  const date = new Date(day.value + 'T00:00:00Z')
  date.setUTCDate(date.getUTCDate() - ((date.getUTCDay() + 6) % 7))
  return date.toISOString().slice(0, 10)
})
const selected = computed(() => data.value[day.value])
const projects = computed(() => selected.value?.projects ?? [])
const displayedDay = computed(() => new Intl.DateTimeFormat('el-GR', {
  timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'long',
}).format(new Date(day.value + 'T00:00:00Z')))
const reportState = computed(() => approved.value.includes(day.value) ? 'Εγκεκριμένη' :
  pending.value.includes(day.value) ? 'Προς έγκριση' : 'Χωρίς αναφορά')
const collectionState = computed(() => {
  if (loading.value && !selected.value) return 'Γίνεται έλεγχος'
  if (failed.value) return 'Ο έλεγχος δεν ήταν διαθέσιμος'
  return { checked: 'Ελέγχθηκε', partial: 'Μερικός έλεγχος', unchecked: 'Εκκρεμεί έλεγχος' }[
    selected.value?.state ?? 'unchecked'
  ]
})

async function refresh() {
  request?.abort()
  const controller = new AbortController()
  request = controller
  const week = start.value
  today.value = athensDay()
  loading.value = true
  failed.value = false
  const timeout = setTimeout(() => controller.abort(), 15000)
  const options = { cache: 'no-store', signal: controller.signal }
  await Promise.allSettled([
    (async () => {
      try {
        const response = await fetch('/api/week?start=' + week, options)
        if (!response.ok) throw new Error()
        const { days } = await response.json()
        if (request === controller) data.value = Object.fromEntries(days.map(item => [item.date, item]))
      } catch {
        if (request === controller) failed.value = true
      }
    })(),
    (async () => {
      try {
        const response = await fetch('/api/scheduled', options)
        if (!response.ok) return
        const { dates } = await response.json()
        if (request === controller) pendingDates.value = dates
      } catch {
        // The week can be browsed even if the separate queue is temporarily offline.
      }
    })(),
  ])
  clearTimeout(timeout)
  if (request === controller) loading.value = false
}

watch(start, () => {
  data.value = {}
  if (props.active) void refresh()
})
watch(() => props.active, active => {
  clearInterval(interval)
  if (active) {
    void refresh()
    interval = setInterval(refresh, 60000)
  } else {
    request?.abort()
  }
}, { immediate: true })
onUnmounted(() => { clearInterval(interval); request?.abort() })

function pullRequests(project) {
  return project.commits.flatMap(commit => {
    const match = /pull request #([0-9]+)/i.exec(commit.subject)
    return match ? [{ id: match[1], sha: commit.sha }] : []
  })
}
</script>

<template>
  <section class="week-overview" aria-labelledby="week-title">
    <header class="view-heading">
      <div><h2 id="week-title" tabindex="-1">Εβδομάδα</h2><p class="muted">Δραστηριότητα εταιρικών projects · Ώρα Αθήνας</p></div>
      <v-btn variant="tonal" :loading="loading" @click="refresh">Ανανέωση</v-btn>
    </header>
    <WeekStrip :day="day" :today="today" :approved="approved" :pending="pending"
               :activity="data" @select="day = $event" />
    <div class="overview-grid">
      <section class="overview-projects" :aria-busy="loading">
        <div class="overview-heading">
          <h3>{{ displayedDay }}</h3>
          <span v-if="selected?.state !== 'unchecked' && !failed && selected" class="overview-count">
            {{ projects.length }} {{ projects.length === 1 ? 'project' : 'projects' }}
          </span>
        </div>
        <p v-if="!projects.length" class="muted overview-empty" role="status">
          {{ selected?.state === 'checked' && !failed ? 'Δεν βρέθηκε τεκμηριωμένη δραστηριότητα.' : collectionState }}
        </p>
        <div v-else :key="day" class="activity-grid enter">
          <article v-for="project in projects" :key="project.name" class="activity-card">
            <h4>{{ project.name }}</h4>
            <p>{{ project.summary }}</p>
            <details>
              <summary>Στοιχεία Git</summary>
              <p class="muted">{{ project.source }}</p>
              <p><strong>Commits</strong></p>
              <ul><li v-for="commit in project.commits" :key="commit.sha"><code>{{ commit.sha }}</code> {{ commit.subject }}</li></ul>
              <p><strong>Ενδείξεις push</strong></p>
              <ul v-if="project.pushes.length"><li v-for="(push, index) in project.pushes" :key="index">{{ push.time }} · {{ push.branch }} · <code>{{ push.sha }}</code></li></ul>
              <p v-else class="muted">Δεν βρέθηκαν.</p>
              <template v-if="pullRequests(project).length">
                <p><strong>PR στο τοπικό Git</strong></p>
                <ul><li v-for="pr in pullRequests(project)" :key="pr.sha">#{{ pr.id }} · <code>{{ pr.sha }}</code></li></ul>
              </template>
            </details>
          </article>
        </div>
      </section>
      <aside class="overview-day">
        <h3>Κατάσταση ημέρας</h3>
        <dl>
          <div><dt>Συλλογή</dt><dd>{{ collectionState }}</dd></div>
          <div><dt>Αναφορά</dt><dd>{{ reportState }}</dd></div>
        </dl>
        <p v-if="selected?.unavailable.length" class="notice">Εκκρεμούν {{ selected.unavailable.join(', ') }}.</p>
        <v-btn v-if="pending.includes(day)" color="primary" @click="emit('standup', { date: day })">Άνοιγμα προσχεδίου</v-btn>
        <v-btn v-else-if="approved.includes(day)" color="primary" variant="tonal"
               @click="emit('standup', { date: day })">Προβολή αναφοράς</v-btn>
        <v-btn v-else color="primary" @click="emit('standup', { date: day, generate: true })">Δημιουργία προσχεδίου</v-btn>
      </aside>
    </div>
  </section>
</template>
