<script setup>
import { onUnmounted, ref, watch } from 'vue'
import AgentIcon from './AgentIcon.vue'
import AgentInstall from './AgentInstall.vue'
import '../styles/tools.css'

const props = defineProps({ active: Boolean })
const status = ref(null)
const busyId = ref('')
const sent = ref('')
const installing = ref(false)
let poll
let timer

async function load() {
  if (document.hidden) return
  try {
    const response = await fetch('/api/agent/status', { cache: 'no-store' })
    if (response.ok) status.value = await response.json()
  } catch { /* keep the last state */ }
}
watch(() => props.active, active => {
  clearInterval(poll)
  if (active) {
    void load()
    poll = setInterval(load, 4000)
  }
}, { immediate: true })
onUnmounted(() => { clearInterval(poll); clearTimeout(timer) })

async function launch(item) {
  if (busyId.value) return
  busyId.value = item.id
  try {
    const response = await fetch('/api/agent/launch', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: item.id }),
    })
    sent.value = response.ok ? `Εκκίνηση: ${item.label}` : 'Ο agent δεν απάντησε. Δοκίμασε ξανά.'
  } catch {
    sent.value = 'Δεν υπάρχει σύνδεση με το tablet.'
  } finally {
    busyId.value = ''
    clearTimeout(timer)
    timer = setTimeout(() => { sent.value = '' }, 3500)
  }
}
</script>

<template>
  <section class="tools" aria-labelledby="tools-title">
    <header class="tools-head">
      <h2 id="tools-title" tabindex="-1">Εργαλεία Windows</h2>
      <span v-if="status?.connected" class="tools-state tools-on">Ο agent είναι συνδεδεμένος</span>
      <span v-else class="tools-state">Ο agent δεν είναι συνδεδεμένος</span>
      <span class="tools-sent" role="status">{{ sent }}</span>
    </header>

    <div v-if="status?.connected" class="tools-grid">
      <button v-for="item in status.launcher" :key="item.id" type="button" class="tool" :class="{ 'is-busy': busyId === item.id }"
              :aria-label="'Άνοιγμα: ' + item.label" @click="launch(item)">
        <AgentIcon :icon="item.icon" />
        <span>{{ item.label }}</span>
      </button>
    </div>

    <div v-else class="tools-empty">
      <p>Τα κουμπιά εμφανίζονται όταν τρέχει ο agent στα Windows. Άνοιξε το <b>start.bat</b> από τον φάκελο του agent και περίμενε λίγα δευτερόλεπτα.</p>
      <v-btn color="primary" @click="installing = true">Πρώτη φορά; Εγκατάσταση στα Windows</v-btn>
    </div>
    <AgentInstall v-model="installing" />
  </section>
</template>
