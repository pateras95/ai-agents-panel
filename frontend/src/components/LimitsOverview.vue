<script setup>
defineProps({ limits: Array, loading: Boolean, error: Boolean })
defineEmits(['refresh'])
</script>

<template>
  <section aria-labelledby="limits-title">
    <header class="view-heading">
      <div><h2 id="limits-title" tabindex="-1">Όρια χρήσης</h2><p class="muted">Ώρα Αθήνας</p></div>
      <v-btn variant="tonal" :loading="loading" @click="$emit('refresh')">Ανανέωση</v-btn>
    </header>
    <p v-if="error" class="notice" role="status">Η τελευταία ανάγνωση απέτυχε.</p>
    <div class="limits-list">
      <article v-for="limit in limits" :key="limit.tool + limit.window" class="limit-row">
        <div><h3>{{ limit.tool }} · {{ limit.window === '7 ημέρες' ? '7ήμερο' : limit.window }}</h3>
          <strong class="metric-value">{{ limit.remaining }}</strong></div>
        <dl class="metric-meta">
          <div><dt>Επαναφορά</dt><dd>{{ limit.reset }}</dd></div>
          <div><dt>Τελευταία ενημέρωση</dt><dd>{{ limit.updated }}</dd></div>
        </dl>
      </article>
    </div>
  </section>
</template>
