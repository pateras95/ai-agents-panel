<script setup>
defineProps({ reports: { type: Array, required: true } })

function displayDate(date) {
  return date.split('-').reverse().join('/')
}
</script>

<template>
  <section class="standups enter" aria-labelledby="standup-title">
    <div class="section-head">
      <h2 id="standup-title">Ιστορικό αναφορών</h2>
    </div>
    <p v-if="!reports.length" class="muted">Δεν έχουν καταχωριστεί αναφορές.</p>
    <details v-for="(report, index) in reports" :key="report.date" :open="index === 0">
      <summary>
        <time :datetime="report.date">{{ displayDate(report.date) }}</time>
      </summary>
      <div class="report-content">
        <template v-for="section in report.sections" :key="section.label">
          <template v-if="section.items.length">
            <h3>{{ section.label }}</h3>
            <ul>
              <li v-for="(item, itemIndex) in section.items" :key="itemIndex">{{ item }}</li>
            </ul>
          </template>
        </template>
      </div>
    </details>
  </section>
</template>
