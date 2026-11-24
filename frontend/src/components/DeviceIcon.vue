<script setup>
defineProps({ kind: { type: String, default: 'generic' } })
// Simple 24px outline icons, one per device type.
const paths = {
  phone: ['M8 2h8a2 2 0 0 1 2 2v16a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2z', 'M11 18.5h2'],
  tablet: ['M6 3h12a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2z', 'M11.5 18h1'],
  computer: ['M5 5h14a1.5 1.5 0 0 1 1.5 1.5V16h-17V6.5A1.5 1.5 0 0 1 5 5z', 'M2 19h20'],
  tv: ['M5 5h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z', 'M8 21h8', 'M12 18v3'],
  speaker: ['M9 2h6a3 3 0 0 1 3 3v14a3 3 0 0 1-3 3H9a3 3 0 0 1-3-3V5a3 3 0 0 1 3-3z', 'M12 17.5a3 3 0 1 0 0-6 3 3 0 0 0 0 6z', 'M12 7h.01'],
  camera: ['M4 7h10a2 2 0 0 1 2 2v6a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V9a2 2 0 0 1 2-2z', 'M16 11l6-3v8l-6-3'],
  router: ['M5 14h14a2 2 0 0 1 2 2v2a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-2a2 2 0 0 1 2-2z', 'M7.5 17h.01', 'M11 17h.01', 'M8.5 11.2a5 5 0 0 1 7 0', 'M6 8.4a8.5 8.5 0 0 1 12 0'],
  vacuum: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M12 14.5a2.5 2.5 0 1 0 0-5 2.5 2.5 0 0 0 0 5z', 'M12 3.5v3', 'M19 8l-2.6 1.5'],
  printer: ['M7 9V3h10v6', 'M5 9h14a2 2 0 0 1 2 2v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-5a2 2 0 0 1 2-2z', 'M7 14h10v7H7z'],
  console: ['M7 7h10a5 5 0 0 1 0 10H7A5 5 0 0 1 7 7z', 'M7.5 12h4', 'M9.5 10v4', 'M15.5 11.5h.01', 'M17.5 13.5h.01'],
  iot: ['M8 7h8a1 1 0 0 1 1 1v8a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V8a1 1 0 0 1 1-1z', 'M9.5 3v2.5', 'M14.5 3v2.5', 'M9.5 18.5V21', 'M14.5 18.5V21', 'M3 9.5h2.5', 'M3 14.5h2.5', 'M18.5 9.5H21', 'M18.5 14.5H21'],
  generic: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18z', 'M9.5 9.5a2.5 2.5 0 1 1 3.6 2.2c-.7.4-1.1.9-1.1 1.8', 'M12 17h.01'],
}
</script>

<template>
  <svg class="device-icon" viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor"
       stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round">
    <path v-for="(d, index) in paths[kind] ?? paths.generic" :key="index" :d="d" />
  </svg>
</template>
