<script setup>
defineProps({ icon: { type: String, default: 'generic' } })
// Simple generic outline glyphs (not the brands' logos), 24px grid.
const paths = {
  spotify: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M7 9.5c3.2-1 7-.7 10 1', 'M7.6 12.6c2.6-.7 5.4-.5 7.8.9', 'M8.3 15.4c2-.5 4-.3 5.7.6'],
  chrome: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7z', 'M12 8.5h8.2', 'M8.9 13.8L4.8 6.7', 'M15.1 13.8l-4.1 7.1'],
  folder: ['M3 7a2 2 0 0 1 2-2h4l2 2.5h8a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z'],
  steam: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M15.5 11a2 2 0 1 0 0-4 2 2 0 0 0 0 4z', 'M3.4 13l5.3 2.1', 'M8.7 15.1a1.9 1.9 0 1 0 1.4 3.5 1.9 1.9 0 0 0-1.4-3.5z', 'M10.3 14.3l4-3.5'],
  epic: ['M5 4h14v10c0 3-3.5 5.2-7 6.5C8.5 19.200 5 17 5 14z', 'M9.500 8.500h5', 'M9.500 8.500v6.500h5', 'M9.500 11.800h3.800'],
  discord: ['M7 7.5c3-1.4 7-1.4 10 0 1.700 3 2.500 6 2.300 9-2 1.500-4 1.800-5 1.800l-.8-1.400', 'M7 7.500c-1.700 3-2.500 6-2.300 9 2 1.500 4 1.800 5 1.800l.8-1.400', 'M9.500 12.500h.01', 'M14.500 12.500h.01'],
  terminal: ['M4 5h16a1.500 1.500 0 0 1 1.500 1.500v11A1.500 1.500 0 0 1 20 19H4a1.500 1.500 0 0 1-1.500-1.500v-11A1.500 1.500 0 0 1 4 5z', 'M7 10l3 2.500L7 15', 'M12.500 15H17'],
  monitor: ['M3 12h4l2-6 3 12 2.500-8 1.500 2H21'],
  generic: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M9.500 9.500a2.500 2.500 0 1 1 3.600 2.200c-.7.4-1.100.9-1.100 1.800', 'M12 17h.01'],
}
</script>

<template>
  <svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">
    <path v-for="(d, index) in paths[icon] ?? paths.generic" :key="index" :d="d" />
  </svg>
</template>
