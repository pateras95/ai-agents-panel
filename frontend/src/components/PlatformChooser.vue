<script setup>
import { onMounted, ref } from 'vue'
import AgentInstall from './AgentInstall.vue'

const props = defineProps({ detected: { type: String, default: null } })
const emit = defineEmits(['choose'])
const options = [
  { id: 'linux', title: 'Ubuntu / Linux', note: 'Όλο το panel: αρχική, εβδομάδα, σύστημα, YouTube και δίκτυο.' },
  { id: 'windows', title: 'Windows', note: 'Σύστημα, εργαλεία (κουμπιά εκκίνησης), YouTube και δίκτυο.' },
]
const last = ref('')
const installing = ref(false)
onMounted(() => {
  try { last.value = localStorage.getItem('nexus-platform') ?? '' } catch { /* the choice is simply not remembered */ }
})
</script>

<template>
  <main class="chooser" aria-labelledby="chooser-title">
    <div class="chooser-logo" aria-hidden="true">NEXUS <span>AI</span></div>
    <h1 id="chooser-title">Σε ποιο σύστημα βρίσκεσαι;</h1>
    <div class="chooser-options">
      <button v-for="option in options" :key="option.id" type="button" class="chooser-card"
              :class="{ 'is-detected': detected === option.id, 'is-last': !detected && last === option.id }"
              @click="emit('choose', option.id)">
        <svg v-if="option.id === 'windows'" viewBox="0 0 24 24" aria-hidden="true" fill="currentColor">
          <path d="M3 5.5l7.5-1v7H3zM11.5 4.3L21 3v8.5h-9.5zM3 12.5h7.5v7L3 18.5zM11.5 12.5H21V21l-9.5-1.3z"/>
        </svg>
        <svg v-else viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
          <rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M7 9l3 3-3 3M12.5 15H17"/>
        </svg>
        <strong>{{ option.title }}</strong>
        <span>{{ option.note }}</span>
        <small v-if="detected === option.id" class="chooser-badge">Συνδεδεμένος συλλέκτης</small>
        <small v-else-if="!detected && last === option.id" class="chooser-badge chooser-last">Τελευταία επιλογή</small>
      </button>
    </div>
    <v-btn variant="text" class="chooser-install" @click="installing = true">Πρώτη φορά στα Windows; Εγκατάσταση agent</v-btn>
    <AgentInstall v-model="installing" />
  </main>
</template>
