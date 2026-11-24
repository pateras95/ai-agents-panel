<script setup>
import { computed } from 'vue'
import { levelColor } from '../composables/useQuotas'

const props = defineProps({
  percent: { type: Number, default: null },
  text: { type: String, default: '' },
  color: { type: String, default: '' },
  size: { type: Number, default: 64 },
  stroke: { type: Number, default: 9 },
})
const RADIUS = 40
const circumference = 2 * Math.PI * RADIUS
const offset = computed(() => circumference * (1 - Math.max(0, Math.min(100, props.percent ?? 0)) / 100))
const tone = computed(() => props.color || levelColor(props.percent))
</script>

<template>
  <div class="q-dial" :style="{ width: size + 'px', height: size + 'px', '--qc': tone }" aria-hidden="true">
    <svg viewBox="0 0 100 100">
      <circle class="bg" cx="50" cy="50" :r="RADIUS" :stroke-width="stroke" :class="{ empty: percent === null }" />
      <circle v-if="percent !== null" class="fg" cx="50" cy="50" :r="RADIUS" :stroke-width="stroke"
              :stroke-dasharray="circumference" :stroke-dashoffset="offset" />
    </svg>
    <span class="q-pct">{{ text }}</span>
  </div>
</template>
