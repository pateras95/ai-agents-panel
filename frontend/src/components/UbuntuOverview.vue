<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import QuotaRing from './QuotaRing.vue'

const props = defineProps({ active: Boolean, pairingTicket: String })
const emit = defineEmits(['paired'])
const DEVICE_KEY = 'nexus-spotify-device'
sessionStorage.removeItem('nexus-spotify-control')
const snapshot = ref(null)
const stale = ref(false)
const loading = ref(false)
const runningAction = ref(false)
const bridge = window.NexusDevice // present inside the Android app, which keeps the grant across address changes
const controlKey = ref(localStorage.getItem(DEVICE_KEY) || bridge?.load() || '')
if (controlKey.value) localStorage.setItem(DEVICE_KEY, controlKey.value)
function syncDevice(event) {
  if (event.key === DEVICE_KEY) controlKey.value = event.newValue || ''
}
window.addEventListener('storage', syncDevice)
const authError = ref('')
const pairingMessage = ref('')
const linking = ref(false)
const controlDialog = ref(false)
const metricsDialog = ref(false)
let poll
let request

const player = computed(() => snapshot.value?.spotify)
const cpu = computed(() => snapshot.value?.metrics.cpu)
const gpu = computed(() => snapshot.value?.metrics.gpu)
const ram = computed(() => snapshot.value?.metrics.ram)
const sensors = computed(() => snapshot.value?.metrics.temperatures ?? [])
const temperatures = computed(() => [
  { label: 'CPU', reading: sensors.value.find(sensor => sensor.sensor.startsWith('Package id')) },
  { label: 'GPU', reading: sensors.value.find(sensor => sensor.sensor === 'GPU') },
])
const gauges = computed(() => [
  { label: 'CPU', reading: cpu.value, color: '#62bdb0', sub: '' },
  { label: 'GPU', reading: gpu.value, color: '#9bc26a', sub: gpu.value?.device?.replace('NVIDIA GeForce ', '') ?? '' },
  { label: 'RAM', reading: ram.value, color: '#a396d6',
    sub: ram.value?.usedGiB == null ? '' : `${ram.value.usedGiB} / ${ram.value.totalGiB} GiB` },
])
const heat = computed(() => [
  { label: 'CPU', reading: sensors.value.find(sensor => sensor.sensor.startsWith('Package id')) },
  { label: 'GPU', reading: sensors.value.find(sensor => sensor.sensor === 'GPU') },
  { label: 'SSD', reading: sensors.value.find(sensor => sensor.device === 'nvme' && sensor.sensor === 'Composite') },
].map(item => {
  const degrees = item.reading?.value ?? null
  const color = degrees === null ? 'var(--dim)' : degrees < 60 ? '#7cc79a' : degrees < 80 ? '#d8b56d' : '#df8b86'
  return { ...item, degrees, color, fill: degrees === null ? 0 : Math.min(100, degrees) }
}))
const usageRows = computed(() => [
  { label: 'CPU', reading: cpu.value },
  { label: 'GPU', reading: gpu.value },
  { label: 'RAM', reading: ram.value },
])
const controls = computed(() => [
  { action: 'previous', label: 'Προηγούμενο' },
  player.value?.state === 'playing'
    ? { action: 'pause', label: 'Παύση' }
    : { action: 'play', label: 'Αναπαραγωγή' },
  { action: 'next', label: 'Επόμενο' },
])
const states = { playing: 'Αναπαραγωγή', paused: 'Σε παύση', stopped: 'Σταματημένο',
  closed: 'Το Spotify είναι κλειστό', unavailable: 'Ο player δεν είναι προσβάσιμος' }
const clock = new Intl.DateTimeFormat('el-GR', { timeZone: 'Europe/Athens', timeStyle: 'medium' })
const time = iso => iso ? clock.format(new Date(iso)) : 'Μη διαθέσιμο'
function value(metric) {
  return metric?.value == null ? 'Μη διαθέσιμο' : `${metric.value}${metric.unit}`
}

async function refresh() {
  if (document.hidden || loading.value) return
  request = new AbortController()
  const controller = request
  const timeout = setTimeout(() => controller.abort(), 8000)
  loading.value = true
  try {
    const response = await fetch('/api/ubuntu', { cache: 'no-store', signal: controller.signal })
    if (!response.ok) throw new Error()
    snapshot.value = await response.json()
    stale.value = false
  } catch {
    if (props.active) stale.value = true
  } finally {
    clearTimeout(timeout)
    if (request === controller) loading.value = false
  }
}

function onVisible() {
  if (props.active && !document.hidden) void refresh()
}
watch(() => props.active, active => {
  clearInterval(poll)
  document.removeEventListener('visibilitychange', onVisible)
  if (active) {
    void refresh()
    poll = setInterval(refresh, 5000)
    document.addEventListener('visibilitychange', onVisible)
  } else {
    request?.abort()
  }
}, { immediate: true })
onUnmounted(() => {
  clearInterval(poll)
  request?.abort()
  document.removeEventListener('visibilitychange', onVisible)
  window.removeEventListener('storage', syncDevice)
})

async function send(payload, secret) {
  const response = await fetch('/api/spotify', {
    method: 'POST', cache: 'no-store',
    headers: { 'Content-Type': 'application/json', Authorization: 'Bearer ' + secret },
    body: JSON.stringify(payload),
  })
  if (response.status === 401) {
    if (controlKey.value === secret) {
      controlKey.value = ''
      localStorage.removeItem(DEVICE_KEY)
      bridge?.clear()
    }
    throw new Error('Η εξουσιοδότηση έληξε ή ανακλήθηκε. Σάρωσε νέο QR.')
  }
  if (!response.ok) throw new Error('Ο Spotify player δεν εκτέλεσε την ενέργεια.')
  return response.json()
}

onMounted(async () => {
  if (!controlKey.value || props.pairingTicket) return
  try {
    await send({ action: 'authorize' }, controlKey.value)
  } catch (error) {
    authError.value = error.message
  }
})

async function pair(ticket) {
  if (!ticket || linking.value) return
  linking.value = true
  authError.value = ''
  pairingMessage.value = ''
  try {
    const response = await fetch('/api/spotify/pair', {
      method: 'POST', cache: 'no-store', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ticket }),
    })
    if (response.status === 410) throw new Error('Το QR έληξε ή χρησιμοποιήθηκε. Άνοιξε νέο QR στο Ubuntu.')
    if (!response.ok) throw new Error('Η σύζευξη δεν ολοκληρώθηκε. Βεβαιώσου ότι είσαι στο ίδιο Wi‑Fi.')
    const { token } = await response.json()
    localStorage.setItem(DEVICE_KEY, token)
    bridge?.save(token)
    controlKey.value = token
    pairingMessage.value = 'Ο χειρισμός Spotify ενεργοποιήθηκε και αποθηκεύτηκε σε αυτή τη συσκευή.'
  } catch (error) {
    authError.value = error.message
  } finally {
    linking.value = false
    emit('paired')
  }
}
watch(() => props.pairingTicket, ticket => { void pair(ticket) }, { immediate: true })

async function disconnect() {
  if (runningAction.value) return
  runningAction.value = true
  authError.value = ''
  pairingMessage.value = ''
  try {
    await send({ action: 'revoke' }, controlKey.value)
    localStorage.removeItem(DEVICE_KEY)
    bridge?.clear()
    controlKey.value = ''
    pairingMessage.value = 'Η εξουσιοδότηση αυτής της συσκευής ανακλήθηκε.'
  } catch (error) {
    authError.value = error.message
  } finally {
    runningAction.value = false
  }
}

async function command(action, value) {
  if (runningAction.value || stale.value || !controlKey.value || !player.value?.actions.includes(action)) return
  runningAction.value = true
  authError.value = ''
  try {
    const result = await send({ action, value }, controlKey.value)
    if (snapshot.value) snapshot.value = { ...snapshot.value, spotify: result.spotify }
  } catch (error) {
    authError.value = error.message
  } finally {
    runningAction.value = false
  }
}
</script>

<template>
  <section class="ubuntu-page" aria-labelledby="ubuntu-title">
    <header class="view-heading">
      <h2 id="ubuntu-title" tabindex="-1">Σύστημα</h2>
      <p v-if="stale" class="notice" role="status">Η ενημέρωση διακόπηκε προσωρινά.</p>
    </header>

    <div class="ubuntu-grid">
      <article class="spotify-panel" aria-label="Spotify" :class="{ playing: player?.state === 'playing' }"
               :style="player?.artwork ? { '--cover': `url(${JSON.stringify(player.artwork)})` } : {}">
        <div class="spotify-cover">
          <img v-if="player?.artwork" :src="player.artwork" referrerpolicy="no-referrer" alt="Εξώφυλλο κομματιού">
          <span v-else aria-hidden="true">♫</span>
        </div>
        <div class="spotify-heading">
          <span class="spotify-brand"><span aria-hidden="true" class="spotify-mark"><i></i><i></i><i></i></span>Spotify</span>
          <v-dialog v-model="controlDialog" max-width="420" aria-labelledby="spotify-control-title">
            <template #activator="{ props: activator }">
              <v-btn v-bind="activator" variant="text" class="quiet-button">Χειρισμός</v-btn>
            </template>
            <v-card class="dialog-panel">
              <div class="dialog-heading">
                <h2 id="spotify-control-title">Χειρισμός Spotify</h2>
                <v-btn variant="text" @click="controlDialog = false">Κλείσιμο</v-btn>
              </div>
              <p v-if="linking" class="muted" role="status">Γίνεται σύζευξη…</p>
              <p v-else-if="!controlKey">Σύζευξη χωρίς QR για το tablet: στο Ubuntu τρέξε <code>python3 -m backend.spotify_pairing --lenovo</code>. Για άλλη συσκευή σάρωσε το <strong>NEXUS Spotify QR</strong>.</p>
              <template v-else>
                <p>Η συσκευή είναι εξουσιοδοτημένη.</p>
                <v-btn variant="text" :disabled="runningAction" @click="disconnect">Αποσύνδεση συσκευής</v-btn>
              </template>
              <p v-if="pairingMessage" class="week-message" role="status">{{ pairingMessage }}</p>
              <p v-if="authError" class="notice" role="status">{{ authError }}</p>
            </v-card>
          </v-dialog>
        </div>
        <div class="spotify-title">
          <h3>{{ player?.title || states[player?.state] || 'Μη διαθέσιμο' }}</h3>
          <p v-if="player?.artist" class="muted">{{ player.artist }}</p>
        </div>
        <div class="spotify-actions">
          <v-btn v-for="control in controls" :key="control.action" class="transport-button"
                 :class="{ 'transport-primary': ['play', 'pause'].includes(control.action) }"
                 :variant="['play', 'pause'].includes(control.action) ? 'flat' : 'text'"
                 :color="['play', 'pause'].includes(control.action) ? 'primary' : undefined"
                 :aria-label="control.label"
                 :disabled="!controlKey || !player?.actions.includes(control.action) || runningAction || stale"
                 @click="command(control.action)">
            <span class="transport-icon" :class="'transport-icon--' + control.action" aria-hidden="true"></span>
          </v-btn>
        </div>
        <label class="volume-control">
          <span>Ένταση Spotify</span>
          <input type="range" min="0" max="100" :value="player?.volume ?? 0"
                 :style="{ '--volume': (player?.volume ?? 0) + '%' }"
                 :disabled="!controlKey || !player?.actions.includes('volume') || runningAction || stale"
                 @input="$event.target.style.setProperty('--volume', $event.target.value + '%')"
                 @change="command('volume', Number($event.target.value))">
          <strong>{{ player?.volume == null ? 'Μη διαθέσιμο' : player.volume + '%' }}</strong>
        </label>
        <p v-if="pairingMessage && !controlDialog" class="week-message" role="status">{{ pairingMessage }}</p>
        <p v-if="authError && !controlDialog" class="notice" role="status">{{ authError }}</p>
      </article>

      <section class="hardware-list" aria-label="Μετρήσεις Ubuntu">
        <div class="gauge-row">
          <div v-for="gauge in gauges" :key="gauge.label" class="gauge-card">
            <QuotaRing :percent="gauge.reading?.value ?? null" :color="gauge.color" :size="104" :stroke="9"
                       :text="gauge.reading?.value == null ? '–' : Math.round(gauge.reading.value) + '%'" />
            <strong>{{ gauge.label }}</strong>
            <small>{{ gauge.reading?.value == null ? 'Μη διαθέσιμο' : (gauge.sub || ' ') }}</small>
          </div>
        </div>
        <div class="heat-row" aria-label="Θερμοκρασίες">
          <div v-for="item in heat" :key="item.label" class="heat-card" :style="{ '--heat': item.color }">
            <span class="heat-label">{{ item.label }}</span>
            <b>{{ item.degrees === null ? 'Μη διαθέσιμο' : Math.round(item.degrees) + '°C' }}</b>
            <i class="heat-bar" aria-hidden="true"><i :style="{ width: item.fill + '%' }"></i></i>
          </div>
        </div>
        <v-dialog v-model="metricsDialog" max-width="550" aria-labelledby="measurements-title">
          <template #activator="{ props: activator }">
            <v-btn v-bind="activator" variant="text" class="quiet-button">Λεπτομέρειες μετρήσεων</v-btn>
          </template>
          <v-card class="dialog-panel measurement-dialog">
            <div class="dialog-heading">
              <h2 id="measurements-title">Λεπτομέρειες μετρήσεων</h2>
              <v-btn variant="text" @click="metricsDialog = false">Κλείσιμο</v-btn>
            </div>
            <p class="muted">Τελευταίες ενημερώσεις · Ώρα Αθήνας</p>
            <dl class="detail-list">
              <div v-for="row in usageRows" :key="row.label">
                <dt>{{ row.label }} <small v-if="row.reading?.device">· {{ row.reading.device }}</small></dt>
                <dd>{{ value(row.reading) }} · {{ time(row.reading?.sampledAt) }}</dd>
              </div>
              <div><dt>Spotify</dt><dd>{{ time(player?.sampledAt) }}</dd></div>
            </dl>
            <h3>Αισθητήρες θερμοκρασίας</h3>
            <p v-if="!sensors.length" class="muted">Μη διαθέσιμο</p>
            <dl v-else class="detail-list">
              <div v-for="(sensor, index) in sensors" :key="index">
                <dt>{{ sensor.device }} · {{ sensor.sensor }}</dt><dd>{{ value(sensor) }} · {{ time(sensor.sampledAt) }}</dd>
              </div>
            </dl>
          </v-card>
        </v-dialog>
      </section>
    </div>
  </section>
</template>
