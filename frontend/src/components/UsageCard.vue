<script setup>
import { computed } from 'vue'

const props = defineProps({
  limit: { type: Object, required: true },
  index: { type: Number, required: true },
})
const unavailable = 'Μη διαθέσιμο'
const isCodex = computed(() => props.limit.tool === 'Codex')
const available = computed(() => props.limit.remaining?.endsWith('%') ?? false)
const percent = computed(() => available.value ? Number.parseFloat(props.limit.remaining) : 0)
</script>

<template>
  <v-card
    tag="article"
    elevation="0"
    class="usage-card enter"
    :class="{ 'usage-card--codex': isCodex }"
    :style="{ '--delay': `${index * 65}ms` }"
  >
    <div class="card-heading">
      <div class="tool">
        <span class="tool-mark" aria-hidden="true">{{ isCodex ? '⌘' : '✳' }}</span>
        <h3>{{ limit.tool }}</h3>
      </div>
      <span class="window">{{ limit.window }}</span>
    </div>
    <p class="reading" :class="{ 'reading--missing': !available }">
      {{ limit.remaining ?? unavailable }}
    </p>
    <p class="field-label">Υπόλοιπο</p>
    <v-progress-linear
      v-if="available"
      :model-value="percent"
      :color="isCodex ? 'secondary' : 'primary'"
      height="5"
      rounded
      aria-label="Ποσοστό υπολοίπου"
    />
    <div v-else class="empty-track" aria-hidden="true"></div>
    <dl class="limit-meta">
      <div><dt>Επαναφορά</dt><dd>{{ limit.reset ?? unavailable }}</dd></div>
      <div><dt>Ενημέρωση</dt><dd>{{ limit.updated ?? unavailable }}</dd></div>
    </dl>
  </v-card>
</template>
