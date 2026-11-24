<script setup>
import { computed, ref, toRef, watch } from 'vue'
import { useWeek } from '../composables/useWeek'
import { buildWeekExport, copyText, groupWeekProjects } from '../composables/useWeekExport'

const props = defineProps({ modelValue: Boolean, reports: { type: Array, required: true } })
const emit = defineEmits(['update:modelValue'])
const which = ref('previous')       // Monday's stand-up reports the week that just ended
const mode = ref('days')
const includePersonal = ref(false)
const copied = ref('')
const open = computed(() => props.modelValue)
const previous = useWeek(open, toRef(props, 'reports'), 60000, -1)
const current = useWeek(open, toRef(props, 'reports'), 60000, 0)
const week = computed(() => which.value === 'previous' ? previous : current)
const projects = computed(() => groupWeekProjects(week.value.days.value, week.value.categories.value, includePersonal.value))
const text = computed(() => buildWeekExport(projects.value, week.value.range.value, mode.value))
const range = computed(() => week.value.range.value)
const loading = computed(() => week.value.loading.value)
watch(() => props.modelValue, isOpen => { if (isOpen) copied.value = '' })

async function copy() {
  copied.value = (await copyText(text.value)) ? 'Αντιγράφηκε.' : 'Επίλεξε το κείμενο και αντίγραψέ το από το μενού της συσκευής.'
}
</script>

<template>
  <v-dialog :model-value="modelValue" fullscreen transition="dialog-bottom-transition" aria-labelledby="export-title"
            @update:model-value="emit('update:modelValue', $event)">
    <v-card class="export-screen">
      <header class="export-bar">
        <h2 id="export-title">Εξαγωγή εβδομάδας</h2>
        <button type="button" class="export-close" aria-label="Κλείσιμο" @click="emit('update:modelValue', false)">
          <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round"><path d="M5 5l14 14M19 5L5 19" /></svg>
        </button>
      </header>
      <div class="export-options">
        <div class="seg" role="group" aria-label="Εβδομάδα">
          <button type="button" :aria-pressed="which === 'previous'" @click="which = 'previous'">Προηγούμενη εβδομάδα</button>
          <button type="button" :aria-pressed="which === 'current'" @click="which = 'current'">Αυτή την εβδομάδα</button>
        </div>
        <div class="seg" role="group" aria-label="Μορφή">
          <button type="button" :aria-pressed="mode === 'days'" @click="mode = 'days'">Ανά ημέρα</button>
          <button type="button" :aria-pressed="mode === 'summary'" @click="mode = 'summary'">Συνοπτικά</button>
        </div>
        <label class="export-toggle"><input v-model="includePersonal" type="checkbox"> Και τα προσωπικά projects</label>
        <span class="export-range">Εβδομάδα {{ range }}</span>
      </div>
      <div class="export-preview" aria-label="Προεπισκόπηση εξαγωγής">
        <p v-if="loading" class="muted">Φόρτωση…</p>
        <p v-else-if="!projects.length" class="muted">Δεν υπάρχει καταγεγραμμένη δουλειά για αυτή την εβδομάδα.</p>
        <article v-for="project in projects" :key="project.name" class="export-project" :style="{ '--pc': project.color }">
          <h3>{{ project.name }}</h3>
          <p v-if="mode === 'summary'" class="export-summary">{{ project.summary }}</p>
          <ul v-else>
            <li v-for="item in project.items" :key="item.date">
              <span class="export-day">{{ item.day }}</span>
              <span class="export-line">{{ item.text }}</span>
            </li>
          </ul>
        </article>
      </div>
      <footer class="export-actions">
        <span v-if="copied" class="muted" role="status">{{ copied }}</span>
        <v-btn color="primary" size="large" :disabled="loading" @click="copy">Αντιγραφή</v-btn>
      </footer>
    </v-card>
  </v-dialog>
</template>
