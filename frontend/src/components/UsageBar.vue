<script setup>
import { onMounted, onUnmounted, ref, toRef } from 'vue'
import QuotaRing from './QuotaRing.vue'
import { useQuotas } from '../composables/useQuotas'

const props = defineProps({ limits: { type: Array, required: true }, loading: Boolean })
const emit = defineEmits(['open', 'resize'])
const dock = ref(null)
const groups = useQuotas(toRef(props, 'limits'), toRef(props, 'loading'))
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
      <button v-for="group in groups" :key="group.name" type="button" class="usage-group"
              :style="{ '--tool': group.color }"
              :aria-label="`Όρια ${group.name}, ${group.values.map(item => item.label + ': ' + item.remaining).join(', ')}`"
              @click="emit('open')">
        <strong class="usage-group-name">{{ group.name }}</strong>
        <span v-for="sample in group.values" :key="sample.wire" class="usage-reading">
          <QuotaRing :percent="sample.percent" :text="sample.percent === null ? '–' : String(Math.round(sample.percent))"
                     :size="46" :stroke="11" />
          <span class="usage-text"><small>{{ sample.label }}</small>
            <b>{{ sample.remaining }}</b></span>
        </span>
      </button>
    </div>
  </footer>
</template>
