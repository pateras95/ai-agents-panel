<script setup>
defineProps({ items: Array, active: String })
const emit = defineEmits(['navigate'])
// Outline icons, 24px grid.
const icons = {
  home: ['M3 11l9-8 9 8', 'M5 10v10h5v-6h4v6h5V10'],
  week: ['M5 4h14a2 2 0 0 1 2 2v13a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2z', 'M3 9h18', 'M8 2v4', 'M16 2v4'],
  daily: ['M9 6h11', 'M9 12h11', 'M9 18h11', 'M4 6l1 1 2-2', 'M4 12l1 1 2-2', 'M4 18l1 1 2-2'],
  system: ['M7 7h10v10H7z', 'M9.5 3v2.5', 'M14.5 3v2.5', 'M9.5 18.5V21', 'M14.5 18.5V21', 'M3 9.5h2.5', 'M3 14.5h2.5', 'M18.5 9.5H21', 'M18.5 14.5H21'],
  youtube: ['M3 8a3 3 0 0 1 3-3h12a3 3 0 0 1 3 3v8a3 3 0 0 1-3 3H6a3 3 0 0 1-3-3z', 'M10 9l5 3-5 3z'],
  network: ['M12 20h.01', 'M8.5 16.4a5 5 0 0 1 7 0', 'M5.5 13a9 9 0 0 1 13 0', 'M2.5 9.5a13 13 0 0 1 19 0'],
}
</script>

<template>
  <nav class="rail" role="tablist" aria-label="Κύρια πλοήγηση" aria-orientation="vertical">
    <div class="rail-logo" aria-hidden="true">N<span>AI</span></div>
    <button v-for="item in items" :key="item.id" type="button" role="tab" class="rail-item"
            :aria-selected="active === item.id" :tabindex="active === item.id ? 0 : -1"
            @click="emit('navigate', item.id)">
      <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.7"
           stroke-linecap="round" stroke-linejoin="round">
        <path v-for="(d, index) in icons[item.icon]" :key="index" :d="d" />
      </svg>
      <span>{{ item.short }}</span>
    </button>
  </nav>
</template>
