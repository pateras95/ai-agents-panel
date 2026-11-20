<script setup>
import UsageCard from './components/UsageCard.vue'
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import AppNavigation from './components/AppNavigation.vue'
import StandupDraft from './components/StandupDraft.vue'

const menus = [
  { id: 'usage', label: 'Όρια χρήσης', heading: 'usage-title' },
  { id: 'standup', label: 'Daily stand-up', heading: 'daily-title' },
]
const active = ref('usage')
function readRoute() {
  active.value = menus.find(item => '#' + item.id === window.location.hash)?.id ?? menus[0].id
}
async function navigate(id) {
  window.location.hash = id
  readRoute()
  await nextTick()
  document.getElementById(menus.find(item => item.id === id).heading)?.focus()
}
readRoute()
onMounted(() => window.addEventListener('hashchange', readRoute))
onUnmounted(() => window.removeEventListener('hashchange', readRoute))
import { useDashboard } from './composables/useDashboard'

const { dashboard, loading, error, refresh } = useDashboard()
</script>

<template>
  <v-app>
    <v-main tag="div">
      <main class="shell">
        <header class="masthead">
          <div class="brand">
            <span class="brand-mark" aria-hidden="true"><i></i><i></i><i></i><i></i></span>
            <h1>NEXUS <span>AI</span></h1>
          </div>
          <AppNavigation mobile :items="menus" :active="active" @navigate="navigate" />
          <v-btn
            v-if="active === 'usage'"
            color="primary"
            variant="tonal"
            rounded="lg"
            :loading="loading"
            @click="refresh"
          >
            <span class="refresh-icon" aria-hidden="true">↻</span>
            Ανανέωση
          </v-btn>
        </header>

        <div class="dashboard-layout">
        <AppNavigation :items="menus" :active="active" @navigate="navigate" />
        <div class="dashboard-content">
        <section v-show="active === 'usage'" class="usage" aria-labelledby="usage-title" :aria-busy="loading">
          <div class="section-head">
            <h2 id="usage-title" tabindex="-1">Όρια χρήσης</h2>
            <span class="timezone">Ώρα Αθήνας</span>
          </div>
          <p v-if="error" class="notice" role="status">
            Η ενημέρωση απέτυχε.{{ dashboard ? ' Εμφανίζονται οι τελευταίες διαθέσιμες τιμές.' : ' Πάτησε Ανανέωση για νέα προσπάθεια.' }}
          </p>
          <div v-if="dashboard" class="usage-grid">
            <UsageCard
              v-for="(limit, index) in dashboard.limits"
              :key="`${limit.tool}-${limit.window}`"
              :limit="limit"
              :index="index"
            />
          </div>
          <div v-else-if="loading" class="usage-grid" aria-label="Φόρτωση ορίων">
            <div v-for="card in 4" :key="card" class="skeleton"></div>
          </div>
        </section>

        <StandupDraft v-show="active === 'standup'" :reports="dashboard?.reports ?? []" @saved="refresh" />
        </div>
        </div>
      </main>
    </v-main>
  </v-app>
</template>
