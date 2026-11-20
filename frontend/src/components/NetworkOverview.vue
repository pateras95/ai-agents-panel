<script setup>
import { computed, onUnmounted, ref, watch } from 'vue'

const props = defineProps({ active: Boolean })
const snapshot = ref(null)
const loading = ref(false)
const failed = ref(false)
const onlineOnly = ref(false)
const detailsOpen = ref(false)
const selected = ref('')
const editing = ref(false)
const saving = ref(false)
const confirming = ref(false)
const lastResponse = ref(null)
const formError = ref('')
const form = ref({ ip: '', name: '', kind: 'generic' })
let interval
let pending

const icons = { generic: '◈', tv: '▣', speaker: '◉', tablet: '▯', computer: '▰', phone: '▯' }
const kinds = { generic: 'Συσκευή', tv: 'Τηλεόραση', speaker: 'Ηχείο', tablet: 'Tablet', computer: 'Υπολογιστής', phone: 'Τηλέφωνο' }
const dateFormat = new Intl.DateTimeFormat('el-GR', { timeZone: 'Europe/Athens', dateStyle: 'short', timeStyle: 'medium' })
const dateTime = stamp => stamp ? dateFormat.format(new Date(stamp)) : 'Μη διαθέσιμο'
const visibleDevices = computed(() => (snapshot.value?.devices ?? []).filter(device => !onlineOnly.value || device.available === true))
const device = computed(() => snapshot.value?.devices.find(item => item.ip === selected.value))
const checks = computed(() => [
  { name: 'Router', state: snapshot.value?.router, ok: 'Απαντά', unavailable: 'Δεν απαντά' },
  { name: 'Internet', state: snapshot.value?.internet, ok: 'Διαθέσιμο', unavailable: 'Χωρίς πρόσβαση' },
])
const deviceState = item => item.available === true ? 'Εντοπίστηκε' : item.available === false ? 'Δεν απαντά' : 'Εκκρεμεί έλεγχος'

async function refresh(force = false) {
  if ((!props.active && !force) || (loading.value && !force)) return
  pending?.abort()
  const controller = new AbortController()
  pending = controller
  const timeout = setTimeout(() => controller.abort(), 5000)
  loading.value = true
  try {
    const response = await fetch('/api/network', { cache: 'no-store', signal: controller.signal })
    if (!response.ok) throw new Error()
    const next = await response.json()
    if (pending === controller) {
      snapshot.value = next
      lastResponse.value = new Date()
      failed.value = false
    }
  } catch {
    if (pending === controller && props.active) failed.value = true
  } finally {
    clearTimeout(timeout)
    if (pending === controller) loading.value = false
  }
}
watch(() => props.active, active => {
  clearInterval(interval)
  if (active) {
    void refresh(true)
    interval = setInterval(() => { if (!document.hidden) void refresh() }, 5000)
  } else pending?.abort()
}, { immediate: true })
onUnmounted(() => { clearInterval(interval); pending?.abort() })

function open(item) {
  confirming.value = false
  selected.value = item?.ip ?? ''
  form.value = item ? { ip: item.ip, name: item.name, kind: item.kind } : { ip: '', name: '', kind: 'generic' }
  editing.value = !item
  formError.value = ''
  detailsOpen.value = true
}

async function save() {
  if (saving.value) return
  saving.value = true
  formError.value = ''
  try {
    const response = await fetch('/api/network/devices', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(form.value),
    })
    if (!response.ok) throw new Error(response.status === 400 ? 'Έλεγξε το όνομα και την τοπική διεύθυνση IPv4.' : 'Η συσκευή δεν αποθηκεύτηκε.')
    detailsOpen.value = false
    await refresh(true)
  } catch (error) {
    formError.value = error.message
  } finally {
    saving.value = false
  }
}
async function removeDevice() {
  if (!device.value || saving.value) return
  saving.value = true
  formError.value = ''
  try {
    const response = await fetch('/api/network/devices', {
      method: 'DELETE', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ip: device.value.ip }),
    })
    if (!response.ok) throw new Error()
    detailsOpen.value = false
    await refresh(true)
  } catch {
    formError.value = 'Η διαγραφή της συσκευής απέτυχε.'
  } finally {
    saving.value = false
  }
}
</script>

<template>
  <section class="network-page" aria-labelledby="network-title">
    <header class="view-heading">
      <div><h2 id="network-title" tabindex="-1">Δίκτυο</h2><p class="muted">Έλεγχος από το Lenovo · Ώρα Αθήνας</p></div>
    </header>
    <article class="network-check backend-health">
      <div>
        <h3>Backend · Lenovo</h3>
        <p>Τελευταία απόκριση · {{ dateTime(lastResponse) }}</p>
      </div>
      <strong class="network-state" role="status" :data-available="failed ? false : lastResponse ? true : null">
        {{ failed ? 'Μη προσβάσιμο' : lastResponse ? 'Σε λειτουργία' : 'Εκκρεμεί έλεγχος' }}
      </strong>
    </article>
    <div class="network-checks">
      <article v-for="check in checks" :key="check.name" class="network-check">
        <h3>{{ check.name }}</h3>
        <strong class="network-state" :data-available="check.state?.available">
          {{ check.state?.available === true ? check.ok : check.state?.available === false ? check.unavailable : 'Εκκρεμεί έλεγχος' }}
        </strong>
        <p>Τελευταίος έλεγχος · {{ dateTime(check.state?.checkedAt) }}</p>
        <p v-if="check.state?.available === false">Τελευταία επιτυχία · {{ dateTime(check.state.lastSuccess) }}</p>
      </article>
    </div>
    <p v-if="snapshot?.router.available && snapshot?.internet.available === false" class="notice" role="status">
      Το router απαντά, αλλά ο έλεγχος πρόσβασης στο Internet απέτυχε.
    </p>
    <p v-if="failed" class="notice" role="status">Το Lenovo δεν έστειλε νεότερα δεδομένα. Εμφανίζονται οι τελευταίες λήψεις.</p>

    <section aria-labelledby="known-title" class="known-devices">
      <div class="known-heading">
        <div>
          <h3 id="known-title">Γνωστές συσκευές</h3>
          <p class="muted">Έλεγχος δηλωμένων IP μέσω ping και τοπικής παρουσίας.</p>
        </div>
        <v-btn color="primary" :disabled="!snapshot" @click="open()">Προσθήκη συσκευής</v-btn>
      </div>
      <label class="network-filter"><input v-model="onlineOnly" type="checkbox"> Μόνο όσες εντοπίστηκαν</label>
      <p v-if="!visibleDevices.length" class="muted">{{ snapshot ? 'Δεν υπάρχουν συσκευές για αυτό το φίλτρο.' : 'Αναμονή για τον πρώτο έλεγχο.' }}</p>
      <div v-else class="network-devices">
        <button v-for="item in visibleDevices" :key="item.ip" type="button" class="network-device" @click="open(item)">
          <span class="network-device-icon" aria-hidden="true">{{ icons[item.kind] ?? icons.generic }}</span>
          <span class="network-device-copy">
            <strong>{{ item.name }}</strong>
            <small class="network-state" :data-available="item.available">{{ deviceState(item) }}</small>
          </span>
        </button>
      </div>
    </section>

    <v-dialog v-model="detailsOpen" max-width="430" aria-labelledby="network-dialog-title">
      <v-card class="dialog-panel">
        <div class="dialog-heading">
          <h2 id="network-dialog-title">{{ device?.name ?? 'Προσθήκη συσκευής' }}</h2>
          <v-btn variant="text" @click="detailsOpen = false">Κλείσιμο</v-btn>
        </div>
        <form v-if="editing" class="network-form" @submit.prevent="save">
          <label>Όνομα<input v-model.trim="form.name" required maxlength="60" placeholder="π.χ. Τηλεόραση σαλονιού"></label>
          <label>Διεύθυνση IPv4<input v-model.trim="form.ip" :readonly="!!selected" required inputmode="decimal" placeholder="192.168.1.x"></label>
          <label>Τύπος
            <select v-model="form.kind"><option v-for="(label, kind) in kinds" :key="kind" :value="kind">{{ label }}</option></select>
          </label>
          <p v-if="formError" class="notice" role="alert">{{ formError }}</p>
          <v-btn color="primary" type="submit" :loading="saving">Αποθήκευση</v-btn>
        </form>
        <template v-else-if="device">
          <dl class="detail-list">
            <div><dt>Κατάσταση</dt><dd>{{ deviceState(device) }}</dd></div>
            <div><dt>IP</dt><dd>{{ device.ip }}</dd></div>
            <div><dt>Τελευταία εμφάνιση</dt><dd>{{ dateTime(device.lastSeen) }}</dd></div>
            <div><dt>Σύνδεση</dt><dd>{{ device.connection ?? 'Μη διαθέσιμο από το router' }}</dd></div>
          </dl>
          <div v-if="confirming" class="network-dialog-actions">
            <p>Να αφαιρεθεί από τις γνωστές συσκευές;</p>
            <v-btn variant="text" :disabled="saving" @click="confirming = false">Ακύρωση</v-btn>
            <v-btn color="error" :loading="saving" @click="removeDevice">Επιβεβαίωση διαγραφής</v-btn>
          </div>
          <div v-else class="network-dialog-actions">
            <v-btn variant="tonal" @click="editing = true">Αλλαγή ονόματος</v-btn>
            <v-btn color="error" variant="text" @click="confirming = true">Διαγραφή</v-btn>
          </div>
          <p v-if="formError" class="notice" role="alert">{{ formError }}</p>
        </template>
      </v-card>
    </v-dialog>
  </section>
</template>
