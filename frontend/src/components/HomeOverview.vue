<script setup>
import { computed, onUnmounted, ref, toRef, watch } from 'vue'
import QuotaRing from './QuotaRing.vue'
import DeviceIcon from './DeviceIcon.vue'
import DayDialog from './DayDialog.vue'
import WeekExport from './WeekExport.vue'
import { STATUS_LABELS, athensDay, previousWorkday, useWeek } from '../composables/useWeek'
import { useQuotas } from '../composables/useQuotas'
import '../styles/home.css'

const props = defineProps({ active: Boolean, limits: { type: Array, required: true }, loading: Boolean, reports: { type: Array, required: true } })
const emit = defineEmits(['navigate', 'standup'])

const { days, summary } = useWeek(toRef(props, 'active'), toRef(props, 'reports'), 60000)
// What is said at tomorrow's stand-up is the work of the last working day, which on a Monday lies in the previous week.
const todayDate = athensDay()
const reportDate = previousWorkday(todayDate)
const needsPrevious = computed(() => props.active && !days.value.some(day => day.date === reportDate))
const previousWeek = useWeek(needsPrevious, toRef(props, 'reports'), 60000, -1)
const daily = computed(() => [...days.value, ...previousWeek.days.value].find(day => day.date === reportDate))
const dialogDay = ref(null)
const dialogOpen = ref(false)
const dialogHeading = ref('')
function openDialog(day, heading) {
  if (!day) return
  dialogDay.value = day
  dialogHeading.value = heading
  dialogOpen.value = true
}
const exporting = ref(false)
const quotas = useQuotas(toRef(props, 'limits'), toRef(props, 'loading'))
const today = computed(() => days.value.find(day => day.today))
const dateTitle = new Intl.DateTimeFormat('el-GR', { timeZone: 'UTC', weekday: 'long', day: 'numeric', month: 'long' })
const todayTitle = computed(() => dateTitle.format(new Date(todayDate + 'T00:00:00Z')))
const dailyTitle = computed(() => dateTitle.format(new Date(reportDate + 'T00:00:00Z')))
const dayDots = { saved: '#7cc79a', draft: '#d8b56d', update: '#7fa8d9', empty: 'var(--dim)', future: 'var(--rule)' }
const shortDay = new Intl.DateTimeFormat('el-GR', { weekday: 'short', timeZone: 'UTC' })

// ---- system, music and network snapshots (only polled while this page is visible)
const system = ref(null)
const network = ref(null)
let systemTimer
let networkTimer
async function load(url, target) {
  if (document.hidden) return
  try {
    const response = await fetch(url, { cache: 'no-store' })
    if (response.ok) target.value = await response.json()
  } catch { /* keep the last snapshot */ }
}
watch(() => props.active, active => {
  clearInterval(systemTimer)
  clearInterval(networkTimer)
  if (active) {
    void load('/api/ubuntu', system)
    void load('/api/network', network)
    systemTimer = setInterval(() => load('/api/ubuntu', system), 5000)
    networkTimer = setInterval(() => load('/api/network', network), 15000)
  }
}, { immediate: true })
onUnmounted(() => { clearInterval(systemTimer); clearInterval(networkTimer) })

const gauges = computed(() => {
  const metrics = system.value?.metrics
  return [
    { label: 'CPU', value: metrics?.cpu?.value ?? null, color: '#62bdb0' },
    { label: 'GPU', value: metrics?.gpu?.value ?? null, color: '#9bc26a' },
    { label: 'RAM', value: metrics?.ram?.value ?? null, color: '#a396d6' },
  ]
})
const heat = computed(() => {
  const sensors = system.value?.metrics?.temperatures ?? []
  return [
    { label: 'CPU', sensor: sensors.find(item => item.sensor.startsWith('Package id')) },
    { label: 'GPU', sensor: sensors.find(item => item.sensor === 'GPU') },
    { label: 'SSD', sensor: sensors.find(item => item.device === 'nvme' && item.sensor === 'Composite') },
  ].map(item => {
    const degrees = item.sensor?.value ?? null
    return { label: item.label, degrees, color: degrees === null ? 'var(--dim)' : degrees < 60 ? '#7cc79a' : degrees < 80 ? '#d8b56d' : '#df8b86' }
  })
})
const player = computed(() => system.value?.spotify)
const playerStates = { playing: 'Αναπαραγωγή', paused: 'Σε παύση', stopped: 'Σταματημένο', closed: 'Το Spotify είναι κλειστό', unavailable: 'Μη διαθέσιμο' }

const DEVICE_KEY = 'nexus-spotify-device'
const busyPlayer = ref(false)
async function control(action) {
  const token = localStorage.getItem(DEVICE_KEY) || window.NexusDevice?.load()
  if (!token || busyPlayer.value || !player.value?.actions.includes(action)) return
  busyPlayer.value = true
  try {
    const response = await fetch('/api/spotify', {
      method: 'POST', cache: 'no-store',
      headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + token },
      body: JSON.stringify({ action }),
    })
    if (response.ok && system.value) system.value = { ...system.value, spotify: (await response.json()).spotify }
  } catch { /* the next poll shows the real state */ } finally {
    busyPlayer.value = false
  }
}

const net = computed(() => {
  const devices = network.value?.devices ?? []
  return {
    router: network.value?.router?.available, internet: network.value?.internet?.available,
    online: devices.filter(item => item.available === true).length, total: devices.length,
    sample: devices.filter(item => item.available === true).slice(0, 6),
  }
})

// Things worth a glance: nearly exhausted limits and a broken connection.
const alerts = computed(() => {
  const list = []
  for (const group of quotas.value) {
    for (const sample of group.values) {
      if (sample.percent !== null && sample.percent <= 15) list.push(`Χαμηλό όριο ${group.name} ${sample.label}: ${sample.remaining}`)
    }
  }
  if (net.value.router === false) list.push('Το router δεν απαντά')
  else if (net.value.internet === false) list.push('Δεν υπάρχει πρόσβαση στο Internet')
  return list
})

function shortReset(text) {
  const found = /(\d{2})\/(\d{2})\/\d{4} (\d{2}:\d{2})/.exec(text ?? '')
  if (!found) return ''
  const now = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Athens', day: '2-digit', month: '2-digit' }).format(new Date())
  return found[1] + '/' + found[2] === now ? found[3] : `${found[1]}/${found[2]} ${found[3]}`
}
</script>

<template>
  <section class="hm" aria-label="Αρχική">
    <ul v-if="alerts.length" class="hm-alerts" role="status">
      <li v-for="text in alerts" :key="text">{{ text }}</li>
    </ul>

    <article class="hm-card hm-daily" :class="'wk-' + (daily?.status ?? 'empty')" role="button" tabindex="0"
             aria-label="Άνοιγμα: Για το daily" @click="openDialog(daily, 'Για το daily')" @keydown.enter.self="openDialog(daily, 'Για το daily')">
      <header>
        <div><small>Για το daily</small><h2>{{ dailyTitle }}</h2></div>
        <span v-if="daily && STATUS_LABELS[daily.status]" class="hm-chip">{{ STATUS_LABELS[daily.status] }}</span>
      </header>
      <div v-if="daily?.rows.length" class="hm-lines">
        <section v-for="group in daily.groups" :key="group.key" :style="{ '--cat': group.color }">
          <h3><span aria-hidden="true"></span>{{ group.label }}</h3>
          <p v-for="item in group.items" :key="item.index"><b v-if="item.row.name">{{ item.row.name }}</b>{{ item.row.text }}</p>
        </section>
      </div>
      <p v-else class="hm-empty">Δεν υπάρχει καταχώριση για την προηγούμενη εργάσιμη ημέρα.</p>
      <footer>
        <v-btn color="primary" size="small" @click.stop="emit('standup', { date: reportDate })">
          {{ daily?.report ? 'Επεξεργασία' : daily?.rows.length ? 'Αποθήκευση' : 'Καταχώριση' }}
        </v-btn>
        <small>Πάτα για όλο το κείμενο</small>
      </footer>
    </article>

    <article class="hm-card hm-today" :class="'wk-' + (today?.status ?? 'empty')" role="button" tabindex="0"
             aria-label="Άνοιγμα: Σήμερα" @click="openDialog(today, 'Σήμερα · για το αυριανό daily')" @keydown.enter.self="openDialog(today, 'Σήμερα · για το αυριανό daily')">
      <header>
        <div><small>Σήμερα · για το αυριανό daily</small><h2>{{ todayTitle }}</h2></div>
        <span v-if="today && STATUS_LABELS[today.status]" class="hm-chip">{{ STATUS_LABELS[today.status] }}</span>
      </header>
      <div v-if="today?.rows.length" class="hm-lines">
        <section v-for="group in today.groups" :key="group.key" :style="{ '--cat': group.color }">
          <h3><span aria-hidden="true"></span>{{ group.label }}</h3>
          <p v-for="item in group.items" :key="item.index"><b v-if="item.row.name">{{ item.row.name }}</b>{{ item.row.text }}</p>
        </section>
      </div>
      <p v-else class="hm-empty">{{ today ? 'Δεν βρέθηκε δραστηριότητα ακόμα. Συγκεντρώνεται από τα commits της ημέρας.' : 'Σήμερα δεν είναι εργάσιμη ημέρα.' }}</p>
      <footer v-if="today">
        <v-btn color="primary" size="small" @click.stop="emit('standup', { date: today.date })">
          {{ today.report ? 'Επεξεργασία' : today.rows.length ? 'Αποθήκευση' : 'Καταχώριση' }}
        </v-btn>
        <small>Πάτα για όλο το κείμενο</small>
      </footer>
    </article>

    <article class="hm-card hm-limits" aria-label="Όρια χρήσης">
      <header><h2>Όρια χρήσης</h2><v-btn variant="text" size="small" @click="emit('navigate', 'usage')">Λεπτομέρειες</v-btn></header>
      <div class="hm-quota-grid">
        <div v-for="group in quotas" :key="group.name" class="hm-quota-group" :style="{ '--tool': group.color }">
          <h3><span aria-hidden="true"></span>{{ group.name }}</h3>
          <div class="hm-rings">
            <div v-for="sample in group.values" :key="sample.wire" class="hm-ring">
              <QuotaRing :percent="sample.percent" :size="72" :stroke="9"
                         :text="sample.percent === null ? '–' : Math.round(sample.percent) + '%'" />
              <b>{{ sample.label }}</b>
              <small>{{ shortReset(sample.reset) ? 'Επαν. ' + shortReset(sample.reset) : '' }}</small>
            </div>
          </div>
        </div>
      </div>
    </article>

    <article class="hm-card hm-week" aria-label="Εβδομάδα">
      <button v-for="day in days" :key="day.date" type="button" class="hm-day" :class="{ 'hm-day-today': day.today }"
              :disabled="day.status === 'future'" @click="emit('standup', { date: day.date })">
        <span class="hm-dot" :style="{ background: dayDots[day.status] }" aria-hidden="true"></span>
        <b>{{ shortDay.format(new Date(day.date + 'T00:00:00Z')) }}</b>
        <small>{{ day.rows.length ? day.rows.length + (day.rows.length === 1 ? ' project' : ' projects') : day.status === 'future' ? '' : '—' }}</small>
      </button>
      <span class="hm-week-sum">{{ summary.saved }}/5 αποθηκευμένα</span>
      <v-btn variant="tonal" size="small" @click="exporting = true">Εξαγωγή εβδομάδας</v-btn>
    </article>

    <article class="hm-card hm-system" aria-label="Σύστημα">
      <header><h2>Σύστημα</h2><v-btn variant="text" size="small" @click="emit('navigate', 'ubuntu')">Άνοιγμα</v-btn></header>
      <div class="hm-gauges">
        <div v-for="gauge in gauges" :key="gauge.label" class="hm-gauge">
          <QuotaRing :percent="gauge.value" :color="gauge.color" :size="64" :stroke="10"
                     :text="gauge.value === null ? '–' : Math.round(gauge.value) + '%'" />
          <b>{{ gauge.label }}</b>
        </div>
      </div>
      <div class="hm-heat">
        <span v-for="item in heat" :key="item.label" :style="{ '--heat': item.color }">
          <small>{{ item.label }}</small><b>{{ item.degrees === null ? '–' : Math.round(item.degrees) + '°' }}</b>
        </span>
      </div>
    </article>

    <article class="hm-card hm-music" aria-label="Spotify" :class="{ playing: player?.state === 'playing' }">
      <div class="hm-cover">
        <img v-if="player?.artwork" :src="player.artwork" referrerpolicy="no-referrer" alt="">
        <span v-else aria-hidden="true">♫</span>
      </div>
      <div class="hm-track">
        <b>{{ player?.title || playerStates[player?.state] || 'Μη διαθέσιμο' }}</b>
        <small>{{ player?.artist || 'Spotify' }}</small>
        <div class="hm-controls">
          <button type="button" aria-label="Προηγούμενο" :disabled="!player?.actions?.includes('previous')" @click="control('previous')">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M6 5v14M19 5v14L9 12z" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
          </button>
          <button type="button" class="hm-play" :aria-label="player?.state === 'playing' ? 'Παύση' : 'Αναπαραγωγή'"
                  :disabled="!player?.actions?.includes(player?.state === 'playing' ? 'pause' : 'play')"
                  @click="control(player?.state === 'playing' ? 'pause' : 'play')">
            <svg v-if="player?.state === 'playing'" viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14M16 5v14" stroke="currentColor" stroke-width="3.5" stroke-linecap="round"/></svg>
            <svg v-else viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z" fill="currentColor"/></svg>
          </button>
          <button type="button" aria-label="Επόμενο" :disabled="!player?.actions?.includes('next')" @click="control('next')">
            <svg viewBox="0 0 24 24" aria-hidden="true"><path d="M18 5v14M5 5v14l10-7z" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linejoin="round"/></svg>
          </button>
        </div>
      </div>
    </article>

    <article class="hm-card hm-net" aria-label="Δίκτυο">
      <header><h2>Δίκτυο</h2><v-btn variant="text" size="small" @click="emit('navigate', 'network')">Άνοιγμα</v-btn></header>
      <div class="hm-checks">
        <span :data-ok="net.router"><i aria-hidden="true"></i>Router</span>
        <span :data-ok="net.internet"><i aria-hidden="true"></i>Internet</span>
      </div>
      <div class="hm-devices">
        <b>{{ net.online }}<small>/{{ net.total }}</small></b>
        <small>συσκευές συνδεδεμένες</small>
        <div class="hm-device-icons"><DeviceIcon v-for="device in net.sample" :key="device.ip" :kind="device.kind" :title="device.name" /></div>
      </div>
    </article>

    <DayDialog v-model="dialogOpen" :day="dialogDay" :heading="dialogHeading" @edit="emit('standup', { date: $event })" />
    <WeekExport v-model="exporting" :reports="reports" />
  </section>
</template>
