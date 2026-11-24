<script setup>
import { STATUS_LABELS } from '../composables/useWeek'
import '../styles/week.css'

defineProps({ modelValue: Boolean, day: Object, heading: String })
const emit = defineEmits(['update:modelValue', 'edit'])
</script>

<template>
  <v-dialog :model-value="modelValue" max-width="62rem" aria-labelledby="day-dialog-title" @update:model-value="emit('update:modelValue', $event)">
    <v-card v-if="day" class="dialog-panel wk-dialog" :class="'wk-' + day.status">
      <div class="dialog-heading">
        <div>
          <small v-if="heading" class="muted">{{ heading }}</small>
          <h2 id="day-dialog-title">{{ day.weekday }} {{ day.label }}</h2>
          <span v-if="STATUS_LABELS[day.status]" class="wk-chip">{{ STATUS_LABELS[day.status] }}</span>
        </div>
        <v-btn variant="text" @click="emit('update:modelValue', false)">Κλείσιμο</v-btn>
      </div>
      <div class="wk-dialog-body">
        <p v-if="!day.rows.length" class="muted">Δεν βρέθηκαν commits ή καταχωρίσεις για αυτή την ημέρα.</p>
        <section v-for="group in day.groups" :key="group.key" class="wk-group" :style="{ '--cat': group.color }">
          <h4><span aria-hidden="true"></span>{{ group.label }}<small>{{ group.sub }}</small></h4>
          <ul class="wk-lines">
            <li v-for="item in group.items" :key="item.index">
              <strong v-if="item.row.name">{{ item.row.name }}</strong>
              <p>{{ item.row.text }}</p>
            </li>
          </ul>
        </section>
        <section v-for="note in day.notes" :key="note.label" class="wk-note">
          <small>{{ note.label }}</small>
          <p v-for="(item, index) in note.items" :key="index">{{ item }}</p>
        </section>
      </div>
      <div class="wk-dialog-actions">
        <v-btn color="primary" @click="emit('update:modelValue', false); emit('edit', day.date)">
          {{ day.report ? 'Επεξεργασία' : day.rows.length ? 'Αποθήκευση' : 'Καταχώριση' }}
        </v-btn>
      </div>
    </v-card>
  </v-dialog>
</template>
