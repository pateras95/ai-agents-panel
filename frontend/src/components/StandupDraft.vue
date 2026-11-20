<script setup>
import { computed, ref } from 'vue'
import StandupHistory from './StandupHistory.vue'

defineProps({ reports: { type: Array, required: true } })
const emit = defineEmits(['saved'])

const dateParts = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'Europe/Athens', year: 'numeric', month: '2-digit', day: '2-digit',
}).formatToParts()
const today = ['year', 'month', 'day'].map(key => dateParts.find(part => part.type === key).value).join('-')
const day = ref(today)
const draft = ref(null)
const completed = ref('')
const next = ref('')
const blockers = ref('')
const confirming = ref(false)
const busy = ref(false)
const error = ref('')
const message = ref('')
const lines = text => text.split('\n').map(line => line.trim()).filter(Boolean)
const canSave = computed(() => draft.value?.date === day.value && lines(completed.value).length > 0)

function reset() {
  draft.value = null
  completed.value = next.value = blockers.value = error.value = message.value = ''
  confirming.value = false
}

async function generate() {
  reset()
  busy.value = true
  try {
    const result = await fetch('/api/draft?' + new URLSearchParams({ date: day.value }))
    if (!result.ok) throw new Error()
    draft.value = await result.json()
    completed.value = draft.value.projects.map(project => `${project.name}: ${project.summary}`).join('\n')
  } catch {
    error.value = 'Η τοπική συλλογή δεν ολοκληρώθηκε. Δοκίμασε ξανά.'
  } finally {
    busy.value = false
  }
}

async function save() {
  if (!confirming.value || !canSave.value) return
  busy.value = true
  error.value = ''
  try {
    const result = await fetch('/api/reports', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        date: draft.value.date, version: draft.value.version, approved: true,
        completed: lines(completed.value), next: lines(next.value), blockers: lines(blockers.value),
      }),
    })
    if (result.status === 409) {
      error.value = 'Η αναφορά άλλαξε. Δημιούργησε νέο προσχέδιο πριν την αντικατάσταση.'
      return
    }
    if (!result.ok) throw new Error()
    reset()
    message.value = 'Η εγκεκριμένη αναφορά αποθηκεύτηκε.'
    emit('saved')
  } catch {
    error.value = 'Η αναφορά δεν αποθηκεύτηκε. Έλεγξε το κείμενο και δοκίμασε ξανά.'
  } finally {
    confirming.value = false
    busy.value = false
  }
}
</script>

<template>
  <section aria-labelledby="daily-title">
    <div class="section-head">
      <h2 id="daily-title" tabindex="-1">Daily stand-up</h2>
      <span class="timezone">Ώρα Αθήνας</span>
    </div>
    <form class="draft-panel" @submit.prevent="generate">
      <label>Ημερομηνία
        <input v-model="day" type="date" required :max="today" :disabled="busy" @change="reset">
      </label>
      <v-btn type="submit" color="primary" variant="tonal" :loading="busy">
        Δημιουργία προσχεδίου
      </v-btn>
    </form>
    <p v-if="error" class="notice" role="alert">{{ error }}</p>
    <p v-if="message" class="notice" role="status">{{ message }}</p>

    <div v-if="draft" class="draft-panel draft-editor">
      <h3>Προσχέδιο</h3>
      <p v-if="!draft.projects.length" class="muted">Δεν βρέθηκε τεκμηριωμένη εργασία. Μπορείς να προσθέσεις γραμμές χειροκίνητα.</p>
      <p v-if="draft.unavailable.length" class="notice">Εκκρεμεί ο τοπικός έλεγχος για {{ draft.unavailable.join(', ') }}.</p>
      <label>Αποτέλεσμα · μία πρόταση ανά project
        <textarea v-model="completed" rows="4" :disabled="busy" @input="confirming = false"></textarea>
      </label>
      <details class="draft-evidence">
        <summary>Αναλυτική προεπισκόπηση</summary>
        <p class="muted">Οι ενδείξεις push είναι από το τοπικό Git. Εκκρεμεί επιβεβαίωση από Bitbucket και Codex.</p>
        <div v-for="project in draft.projects" :key="project.name" class="evidence-project">
          <h4>{{ project.name }}</h4>
          <p>{{ project.source }}</p>
          <p>Τοπικά branches · {{ project.branches.join(', ') || 'Μη διαθέσιμο' }}</p>
          <p>Ενδείξεις push</p>
          <ul v-if="project.pushes.length">
            <li v-for="(push, index) in project.pushes" :key="index">{{ push.time }} · {{ push.branch }} · {{ push.sha }}</li>
          </ul>
          <p v-else>Δεν βρέθηκαν.</p>
          <p>Commits</p>
          <ul>
            <li v-for="commit in project.commits" :key="commit.sha">{{ commit.sha }} · {{ commit.subject }}</li>
          </ul>
        </div>
      </details>
      <details class="draft-evidence">
        <summary>Προσθήκη προαιρετικών σημειώσεων</summary>
        <label>Επόμενα<textarea v-model="next" rows="2" :disabled="busy" @input="confirming = false"></textarea></label>
        <label>Εμπόδια<textarea v-model="blockers" rows="2" :disabled="busy" @input="confirming = false"></textarea></label>
      </details>
      <v-btn v-if="!confirming" color="primary" variant="tonal" :disabled="!canSave || busy"
             @click="confirming = true">Έγκριση αναφοράς</v-btn>
      <div v-else class="approval" role="group" aria-label="Επιβεβαίωση αποθήκευσης">
        <p>{{ draft.version ? 'Να αντικατασταθεί η υπάρχουσα αναφορά αυτής της ημέρας;' : 'Να αποθηκευτεί το προσχέδιο ως εγκεκριμένη αναφορά;' }}</p>
        <v-btn color="primary" :loading="busy" @click="save">Επιβεβαίωση</v-btn>
        <v-btn variant="text" :disabled="busy" @click="confirming = false">Ακύρωση</v-btn>
      </div>
    </div>

    <StandupHistory :reports="reports" />
  </section>
</template>
