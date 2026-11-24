import { computed, onUnmounted, ref, watch } from 'vue'
import { rowsFromProjects, rowsFromReport } from './useDayEntry'
import { groupRows } from './useCategories'

export function athensDay() {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Athens',
    year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts()
  return ['year', 'month', 'day'].map(key => parts.find(part => part.type === key).value).join('-')
}
const parse = date => new Date(date + 'T00:00:00Z')
export function shift(date, days) {
  const value = parse(date)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}
export const mondayOf = date => shift(date, -((parse(date).getUTCDay() + 6) % 7))
const names = new Intl.DateTimeFormat('el-GR', { weekday: 'long', timeZone: 'UTC' })
const dates = new Intl.DateTimeFormat('el-GR', { day: 'numeric', month: 'long', timeZone: 'UTC' })

// The last working day before `date` (Mon-Fri): what is said at the next morning's stand-up.
export function previousWorkday(date) {
  let day = shift(date, -1)
  while ([0, 6].includes(parse(day).getUTCDay())) day = shift(day, -1)
  return day
}

export const STATUS_LABELS = {
  saved: 'Αποθηκευμένο', draft: 'Προσχέδιο από commits', update: 'Νέα δραστηριότητα',
  empty: 'Χωρίς δραστηριότητα', future: '',
}

// The entry of a day is the saved report when there is one, otherwise the live draft from the commits.
export function useWeek(active, reports, intervalMs = 30000, weekOffset = 0) {
  const today = ref(athensDay())
  const monday = ref(shift(today.value, -((parse(today.value).getUTCDay() + 6) % 7) + 7 * weekOffset))
  const data = ref({})
  const categories = ref({})
  const loading = ref(false)
  const failed = ref(false)
  let request
  let interval

  const range = computed(() => `${dates.format(parse(monday.value))} – ${dates.format(parse(shift(monday.value, 4)))}`)
  const canGoForward = computed(() => shift(monday.value, 7) <= today.value)
  const days = computed(() => Array.from({ length: 5 }, (_, index) => {
    const date = shift(monday.value, index)
    const live = data.value[date]
    const report = reports.value.find(item => item.date === date)
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
    if (active.value) void refresh()
  }
  function showWeekOf(date) {
    const target = mondayOf(date)
    if (target === monday.value) return
    monday.value = target
    data.value = {}
    if (active.value) void refresh()
  }
  watch(active, isActive => {
    clearInterval(interval)
    if (isActive) {
      void refresh()
      interval = setInterval(refresh, intervalMs)
    } else {
      request?.abort()
    }
  }, { immediate: true })
  onUnmounted(() => { clearInterval(interval); request?.abort() })

  return { today, monday, days, summary, range, canGoForward, loading, failed, categories, refresh, step, showWeekOf }
}
