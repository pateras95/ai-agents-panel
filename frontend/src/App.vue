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
  { id: 'week', label: 'Εργασίες Εβδομάδας', short: 'Εβδομάδα', heading: 'week-title' },
  { id: 'standup', label: 'Daily stand-up', short: 'Daily', heading: 'daily-title' },
  { id: 'ubuntu', label: 'Σύστημα', short: 'Σύστημα', heading: 'ubuntu-title' },
  { id: 'youtube', label: 'YouTube Growth', short: 'YouTube', heading: 'youtube-title' },
  { id: 'network', label: 'Δίκτυο', short: 'Δίκτυο', heading: 'network-title' },
  // The limits are always visible in the dock; this page opens from there and is not a tab.
  { id: 'usage', label: 'Όρια χρήσης', short: 'Όρια', heading: 'limits-title', hidden: true },
]
const tabs = routes.filter(item => !item.hidden)
const pager = ref(null)
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

let scrolling = 0
function goTo(id, smooth) {
  const index = routes.findIndex(item => item.id === id)
  const element = pager.value
  if (index < 0 || !element) return
  clearTimeout(scrolling)
  element.scrollTo({ left: index * element.clientWidth, behavior: smooth ? 'smooth' : 'instant' })
}
function route() {
  readPairingLink()
  const id = routes.find(menu => '#' + menu.id === window.location.hash)?.id ?? 'week'
  active.value = id
  goTo(id, false)
}
// Swiping the pager changes the active tab; the address follows without adding history entries.
function onScroll() {
  const element = pager.value
  const index = Math.round(element.scrollLeft / element.clientWidth)
  const id = routes[Math.max(0, Math.min(routes.length - 1, index))].id
  if (id !== active.value) {
    active.value = id
    history.replaceState(null, '', '#' + id)
  }
}
async function navigate(id) {
  active.value = id
  history.replaceState(null, '', '#' + id)
  goTo(id, true)
  await nextTick()
  document.getElementById(routes.find(menu => menu.id === id)?.heading)?.focus({ preventScroll: true })
}
function openStandup(request) {
  void navigate('standup')
  standupRequest.value = request
}
function reportChanged() {
  void refreshReports(true)
}
onMounted(() => {
  route()
  window.addEventListener('resize', route)
  window.addEventListener('hashchange', route)
})
onUnmounted(() => {
  window.removeEventListener('hashchange', route)
  window.removeEventListener('resize', route)
})
</script>

<template>
  <v-app :style="{ '--dock-space': dockHeight + 'px' }">
    <v-main tag="div" class="frame-main">
      <div class="frame">
        <header class="masthead">
          <h1 class="wordmark">NEXUS <span>AI</span></h1>
          <AppNavigation :items="tabs" :active="active" @navigate="navigate" />
        </header>

        <main ref="pager" class="pager" @scroll.passive="onScroll">
          <div class="pane pane-fit" role="tabpanel" aria-label="Εργασίες Εβδομάδας"><div class="pane-inner">
            <WeekOverview :active="active === 'week'" :reports="reports" @standup="openStandup" />
          </div></div>
          <div class="pane pane-fit" role="tabpanel" aria-label="Daily stand-up"><div class="pane-inner">
            <StandupDraft :active="active === 'standup'" :request="standupRequest" :reports="reports"
                          :report-error="reportError" @saved="reportChanged" @deleted="reportChanged" />
          </div></div>
          <div class="pane pane-fit" role="tabpanel" aria-label="Σύστημα"><div class="pane-inner">
            <UbuntuOverview :active="active === 'ubuntu'" :pairing-ticket="pairingTicket" @paired="pairingTicket = ''" />
          </div></div>
          <div class="pane" role="tabpanel" aria-label="YouTube Growth"><div class="pane-inner">
            <YouTubeGrowth v-if="active === 'youtube'" />
          </div></div>
          <div class="pane" role="tabpanel" aria-label="Δίκτυο"><div class="pane-inner">
            <NetworkOverview :active="active === 'network'" />
          </div></div>
          <div class="pane pane-fit" role="tabpanel" aria-label="Όρια χρήσης"><div class="pane-inner">
            <LimitsOverview :limits="limits" :loading="loading" :error="error" @refresh="refreshLimits" />
          </div></div>
        </main>
      </div>
    </v-main>
    <UsageBar :limits="limits" :loading="loading" @open="navigate('usage')" @resize="dockHeight = $event" />
  </v-app>
</template>
