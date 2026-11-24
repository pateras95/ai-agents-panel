<script setup>
import { onMounted, onUnmounted, ref, toRef } from 'vue'
import QuotaRing from './QuotaRing.vue'
import { useQuotas } from '../composables/useQuotas'

const props = defineProps({ title: String, limits: { type: Array, required: true }, loading: Boolean, showLimits: { type: Boolean, default: true } })
const emit = defineEmits(['open'])
const groups = useQuotas(toRef(props, 'limits'), toRef(props, 'loading'))
const time = new Intl.DateTimeFormat('el-GR', { timeZone: 'Europe/Athens', hour: '2-digit', minute: '2-digit', hour12: false })
const date = new Intl.DateTimeFormat('el-GR', { timeZone: 'Europe/Athens', weekday: 'short', day: 'numeric', month: 'short' })
const now = ref(new Date())
let tick
onMounted(() => { tick = setInterval(() => { now.value = new Date() }, 15000) })
onUnmounted(() => clearInterval(tick))
</script>

<template>
  <header class="statusbar">
    <h1 class="statusbar-title">{{ title }}</h1>
    <button v-if="showLimits" type="button" class="limits-pill" aria-label="Όρια χρήσης" @click="emit('open')">
      <span v-for="group in groups" :key="group.name" class="limits-group" :style="{ '--tool': group.color }">
        <b>{{ group.name === 'Claude Code' ? 'Claude' : group.name }}</b>
        <span v-for="sample in group.values" :key="sample.wire" class="limits-mini"
              :title="`${group.name} ${sample.label}: ${sample.remaining}`">
          <QuotaRing :percent="sample.percent" :size="30" :stroke="13"
                     :text="sample.percent === null ? '–' : String(Math.round(sample.percent))" />
          <small>{{ sample.label }}</small>
        </span>
      </span>
    </button>
    <div class="clock" aria-live="off">
      <b>{{ time.format(now) }}</b>
      <small>{{ date.format(now) }}</small>
    </div>
  </header>
</template>
