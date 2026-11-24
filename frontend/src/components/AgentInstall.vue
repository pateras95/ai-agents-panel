<script setup>
import { ref } from 'vue'

defineProps({ modelValue: Boolean })
const emit = defineEmits(['update:modelValue'])
const link = ref('')
const message = ref('')
const busy = ref(false)

async function create() {
  busy.value = true
  message.value = ''
  link.value = ''
  try {
    const response = await fetch('/api/agent/pair', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}' })
    if (response.status === 404) throw new Error('Το πακέτο του agent δεν έχει εγκατασταθεί στο tablet. Τρέξε scripts/build_windows_agent.py και scripts/deploy_lenovo.sh στο Ubuntu.')
    if (!response.ok) throw new Error('Δεν δημιουργήθηκε σύνδεσμος. Δοκίμασε ξανά.')
    const { ticket } = await response.json()
    link.value = `${window.location.origin}/agent-download/${ticket}`
  } catch (error) {
    message.value = error.message
  } finally {
    busy.value = false
  }
}
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="52rem" aria-labelledby="agent-title" @update:model-value="emit('update:modelValue', $event)">
    <v-card class="dialog-panel agent-dialog">
      <div class="dialog-heading">
        <h2 id="agent-title">Σύνδεση Windows</h2>
        <v-btn variant="text" @click="emit('update:modelValue', false)">Κλείσιμο</v-btn>
      </div>
      <ol class="agent-steps">
        <li>Πάτησε «Δημιουργία συνδέσμου» εδώ.</li>
        <li>Στα Windows άνοιξε τον σύνδεσμο σε browser (ίδιο Wi-Fi) και κατέβασε το ZIP.</li>
        <li>Αποσυμπίεσέ το κάπου μόνιμα και κάνε διπλό κλικ στο <b>start.bat</b>. Δεν χρειάζεται Python ή άλλη εγκατάσταση.</li>
        <li>Επίλεξε «Windows» στο tablet. Το Σύστημα και τα Εργαλεία συνδέονται μέσα σε λίγα δευτερόλεπτα.</li>
      </ol>
      <p class="muted">Ο σύνδεσμος ισχύει 10 λεπτά και για μία λήψη. Το ZIP περιέχει τον ιδιωτικό κωδικό σύνδεσης με το tablet, οπότε μην το μοιράζεσαι.</p>
      <v-btn color="primary" :loading="busy" @click="create">Δημιουργία συνδέσμου</v-btn>
      <p v-if="link" class="agent-link" role="status">{{ link }}</p>
      <p v-if="message" class="notice" role="alert">{{ message }}</p>
    </v-card>
  </v-dialog>
</template>
