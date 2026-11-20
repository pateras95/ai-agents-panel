<script setup>
import { nextTick, onMounted, onUnmounted, ref } from 'vue'
import UsageBar from './components/UsageBar.vue'
import AppNavigation from './components/AppNavigation.vue'
import StandupDraft from './components/StandupDraft.vue'
import WeekOverview from './components/WeekOverview.vue'
import LimitsOverview from './components/LimitsOverview.vue'
import UbuntuOverview from './components/UbuntuOverview.vue'
import YouTubeGrowth from './components/YouTubeGrowth.vue'
import NetworkOverview from './components/NetworkOverview.vue'
import { useDashboard } from './composables/useDashboard'

const routes = [
  { id: 'week', label: 'Εργασίες Εβδομάδας', heading: 'week-title' },
  { id: 'standup', label: 'Daily stand-up', heading: 'daily-title' },
  { id: 'usage', label: 'Όρια χρήσης', heading: 'limits-title' },
  { id: 'ubuntu', label: 'Σύστημα', heading: 'ubuntu-title' },
  { id: 'youtube', label: 'YouTube Growth', heading: 'youtube-title' },
  { id: 'network', label: 'Δίκτυο', heading: 'network-title' },
]
const menus = routes.filter(route => route.id !== 'usage')
const active = ref('week')
const pairingTicket = ref('')
function readPairingLink() {
  const ticket = new URLSearchParams(window.location.hash.slice(1)).get('spotify-pair')
  if (!ticket) return
  history.replaceState(null, '', '#ubuntu')
  pairingTicket.value = ticket
}
readPairingLink()
const standupRequest = ref(null)
const { limits, loading, error, refreshLimits, reports, reportError, refreshReports } = useDashboard()
const dockHeight = ref(100)

function route() {
  readPairingLink()
  active.value = routes.find(menu => '#' + menu.id === window.location.hash)?.id ?? 'week'
}
async function navigate(id) {
  window.location.hash = id
  route()
  await nextTick()
  document.getElementById(routes.find(menu => menu.id === id)?.heading)?.focus()
}
function openStandup(request) {
  void navigate('standup')
  standupRequest.value = request
}
function reportChanged() {
  void refreshReports(true)
}
route()
onMounted(() => window.addEventListener('hashchange', route))
onUnmounted(() => window.removeEventListener('hashchange', route))
</script>

<template>
  <v-app :style="{ '--dock-space': dockHeight + 'px' }">
    <v-main tag="div">
      <main class="shell shell-with-usage">
        <header class="masthead">
          <h1 class="wordmark">NEXUS <span>AI</span></h1>
          <AppNavigation :items="menus" :active="active" @navigate="navigate" />
        </header>

        <div class="dashboard-content">
            <WeekOverview v-show="active === 'week'" :active="active === 'week'" :reports="reports"
                          @standup="openStandup" />
            <StandupDraft v-show="active === 'standup'" :active="active === 'standup'"
                          :request="standupRequest" :reports="reports" :report-error="reportError"
                          @saved="reportChanged" @deleted="reportChanged" />
            <LimitsOverview v-show="active === 'usage'" :limits="limits" :loading="loading" :error="error" @refresh="refreshLimits" />
            <UbuntuOverview v-show="active === 'ubuntu'" :active="active === 'ubuntu'"
                            :pairing-ticket="pairingTicket" @paired="pairingTicket = ''" />
            <YouTubeGrowth v-if="active === 'youtube'" />
            <NetworkOverview v-show="active === 'network'" :active="active === 'network'" />
        </div>
      </main>
    </v-main>
    <UsageBar :limits="limits" :loading="loading" @open="navigate('usage')" @resize="dockHeight = $event" />
  </v-app>
</template>
