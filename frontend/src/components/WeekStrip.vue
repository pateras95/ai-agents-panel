<script setup>
import { computed } from 'vue'

const props = defineProps({
  day: String, today: String, approved: Array, pending: Array, busy: Boolean, activity: Object,
})
const emit = defineEmits(['select'])
const dateLabel = new Intl.DateTimeFormat('el-GR', { day: 'numeric', month: 'short', timeZone: 'UTC' })
const dayLabel = new Intl.DateTimeFormat('el-GR', { weekday: 'short', timeZone: 'UTC' })
const parse = date => new Date(date + 'T00:00:00Z')
function shift(date, days) {
  const value = parse(date)
  value.setUTCDate(value.getUTCDate() + days)
  return value.toISOString().slice(0, 10)
}

const monday = computed(() => shift(props.day, -((parse(props.day).getUTCDay() + 6) % 7)))
const days = computed(() => Array.from({ length: 7 }, (_, index) => shift(monday.value, index))
  .filter((date, index) => index < 5 || date === props.day || props.approved.includes(date) || props.pending.includes(date)))
const range = computed(() => `${dateLabel.format(parse(monday.value))} – ${dateLabel.format(parse(days.value.at(-1)))}`)
const nextAvailable = computed(() => shift(monday.value, 7) <= props.today)

function changeWeek(offset) {
  const target = shift(props.day, offset * 7)
  emit('select', target > props.today ? props.today : target)
}

function jump(event) {
  const input = event.target
  const value = input.value
  input.value = props.day
  if (value && value <= props.today && /^\d{4}-\d{2}-\d{2}$/.test(value)) emit('select', value)
}

function status(date) {
  if (props.approved.includes(date)) return 'approved'
  if (props.pending.includes(date)) return 'pending'
  return 'empty'
}
function projectLabel(date) {
  const count = props.activity?.[date]?.projects.length ?? 0
  return count === 1 ? '1 project' : `${count} projects`
}
const collectionLabels = { unchecked: 'Εκκρεμεί έλεγχος', partial: 'Μερικός έλεγχος', checked: 'Ελέγχθηκε' }

const statusLabels = { approved: 'Εγκεκριμένη', pending: 'Προς έγκριση', empty: 'Χωρίς αναφορά' }
</script>

<template>
  <section class="week-strip" aria-label="Επιλογή εβδομάδας και ημέρας">
    <div class="week-toolbar">
      <div class="week-period" aria-live="polite">
        <button class="week-step" type="button" aria-label="Προηγούμενη εβδομάδα" :disabled="busy"
                @click="changeWeek(-1)">‹</button>
        <strong>{{ range }}</strong>
        <button class="week-step" type="button" aria-label="Επόμενη εβδομάδα" :disabled="busy || !nextAvailable"
                @click="changeWeek(1)">›</button>
      </div>
      <label class="week-jump"><span>Μετάβαση σε ημερομηνία</span>
        <input type="date" :value="day" :max="today" :disabled="busy"
               @change="jump">
      </label>
    </div>
    <div class="week-days" :style="{ '--day-count': days.length }">
      <button v-for="date in days" :key="date" type="button" class="week-day"
              :aria-pressed="date === day" :aria-current="date === today ? 'date' : undefined"
              :disabled="busy || date > today" @click="emit('select', date)">
        <span class="week-day-heading">
          <span class="week-day-name">{{ dayLabel.format(parse(date)) }}</span>
          <b>{{ dateLabel.format(parse(date)) }}</b>
        </span>
        <span v-if="activity && activity[date]?.state !== 'unchecked' && activity[date]" class="week-day-projects">
          {{ projectLabel(date) }}
        </span>
        <span v-if="activity && activity[date]?.state !== 'checked'" class="week-collection-state">
          {{ collectionLabels[activity[date]?.state ?? 'unchecked'] }}
        </span>
        <span v-if="activity?.[date]?.projects.length" class="week-day-names">
          <span v-for="project in activity[date].projects" :key="project.name" class="week-project-name">
            {{ project.name }}
          </span>
        </span>
        <span class="week-day-state" :data-status="status(date)">{{ statusLabels[status(date)] }}</span>
      </button>
    </div>
  </section>
</template>
