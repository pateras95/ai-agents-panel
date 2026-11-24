<script setup>
import { toRef } from 'vue'
import QuotaRing from './QuotaRing.vue'
import { useQuotas } from '../composables/useQuotas'

const props = defineProps({ limits: Array, loading: Boolean, error: Boolean })
defineEmits(['refresh'])
const groups = useQuotas(toRef(props, 'limits'), toRef(props, 'loading'))
</script>

<template>
  <section aria-labelledby="limits-title">
    <header class="view-heading">
      <div><h2 id="limits-title" tabindex="-1">Όρια χρήσης</h2><p class="muted">Ώρα Αθήνας</p></div>
      <v-btn variant="tonal" :loading="loading" @click="$emit('refresh')">Ανανέωση</v-btn>
    </header>
    <p v-if="error" class="notice" role="status">Η τελευταία ανάγνωση απέτυχε.</p>
    <div class="q-grid">
      <article v-for="group in groups" :key="group.name" class="q-card" :style="{ '--tool': group.color }">
        <header class="q-head">
          <span class="q-dot" aria-hidden="true"></span>
          <h3>{{ group.name }}</h3>
        </header>
        <div class="q-rings">
          <div v-for="sample in group.values" :key="sample.wire" class="q-ring">
            <QuotaRing :percent="sample.percent" :size="132" :stroke="8"
                       :text="sample.percent === null ? '–' : Math.round(sample.percent) + '%'" />
            <strong class="q-label">{{ sample.label }}</strong>
            <span class="q-sub">Υπόλοιπο: {{ sample.remaining }}</span>
            <span class="q-sub">Επαναφορά: {{ sample.reset }}</span>
            <span class="q-sub q-upd">Ενημέρωση: {{ sample.updated }}</span>
          </div>
        </div>
        <p v-if="group.hint && group.values.every(item => item.percent === null) && !loading" class="q-hint">{{ group.hint }}</p>
      </article>
    </div>
  </section>
</template>
