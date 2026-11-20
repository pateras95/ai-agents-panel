<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'

const props = defineProps({ limits: { type: Array, required: true }, loading: Boolean })
const emit = defineEmits(['open', 'resize'])
const dock = ref(null)
const tools = ['Claude Code', 'Codex']
const windows = [{ wire: '5ωρο', label: '5ωρο' }, { wire: '7 ημέρες', label: '7ήμερο' }]
const groups = computed(() => tools.map(tool => ({
  tool,
  values: windows.map(window => {
    const sample = props.limits.find(limit => limit.tool === tool && limit.window === window.wire)
    const remaining = sample?.remaining ?? (props.loading ? '—' : 'Μη διαθέσιμο')
    const percent = remaining.endsWith('%') ? Number.parseFloat(remaining) : null
    return { ...window, remaining, percent }
  }),
})))
let observer
onMounted(() => {
  const measure = () => emit('resize', Math.ceil(dock.value.getBoundingClientRect().height))
  measure()
  observer = new ResizeObserver(measure)
  observer.observe(dock.value)
})
onUnmounted(() => observer?.disconnect())
</script>

<template>
  <footer ref="dock" class="usage-dock" aria-label="Όρια χρήσης" :aria-busy="loading">
    <div class="usage-dock-row">
      <button v-for="group in groups" :key="group.tool" type="button" class="usage-group"
              :aria-label="`Όρια ${group.tool}, ${group.values.map(item => item.label + ': ' + item.remaining).join(', ')}`"
              @click="emit('open')">
        <strong class="usage-group-name">{{ group.tool }}</strong>
        <span v-for="sample in group.values" :key="sample.wire" class="usage-reading">
          <small>{{ sample.label }}</small>
          <b>{{ sample.remaining }}</b>
          <span v-if="sample.percent !== null" class="usage-track" aria-hidden="true">
            <span :style="{ width: Math.max(0, Math.min(100, sample.percent)) + '%' }"></span>
          </span>
        </span>
      </button>
    </div>
  </footer>
</template>
