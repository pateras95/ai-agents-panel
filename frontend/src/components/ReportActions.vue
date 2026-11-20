<script setup>
import { ref, watch } from 'vue'
const props = defineProps({ report: { type: Object, required: true } })
const emit = defineEmits(['deleted'])
const pending = ref(null)
watch(() => props.report.date, () => { pending.value = null })
const busy = ref(false)
const feedback = ref('')

async function deleteReport() {
  if (!pending.value || busy.value) return
  const { date, version } = pending.value
  busy.value = true
  feedback.value = ''
  try {
    const response = await fetch('/api/reports', {
      method: 'DELETE',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ date, version, approved: true }),
    })
    if (response.status === 409 || response.status === 404) {
      feedback.value = 'Η λίστα άλλαξε. Ενημερώθηκε για να δοκιμάσεις ξανά.'
      emit('deleted')
    } else if (!response.ok) {
      throw new Error()
    } else {
      feedback.value = `Η αναφορά της ${displayDate(date)} διαγράφηκε.`
      emit('deleted', date)
    }
    pending.value = null
  } catch {
    feedback.value = 'Η διαγραφή δεν ολοκληρώθηκε. Δοκίμασε ξανά.'
  } finally {
    busy.value = false
  }
}

function displayDate(date) {
  return date.split('-').reverse().join('/')
}
</script>

<template>
  <div>
    <p v-if="feedback" role="status" class="notice">{{ feedback }}</p>
    <div v-if="pending" class="report-actions" role="group"
         :aria-label="`Διαγραφή αναφοράς ${displayDate(report.date)}`">
      <p>Να διαγραφεί οριστικά η αναφορά της {{ displayDate(report.date) }};</p>
      <v-btn color="error" :loading="busy" @click="deleteReport">Οριστική διαγραφή</v-btn>
      <v-btn variant="text" :disabled="busy" @click="pending = null">Ακύρωση</v-btn>
    </div>
    <v-btn v-else color="error" variant="text" :disabled="!report.version"
           @click="pending = report">Διαγραφή αναφοράς</v-btn>
  </div>
</template>
