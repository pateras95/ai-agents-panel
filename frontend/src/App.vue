<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import StatusBar from './components/StatusBar.vue'
import AppRail from './components/AppRail.vue'
import HomeOverview from './components/HomeOverview.vue'
import StandupDraft from './components/StandupDraft.vue'
import LimitsOverview from './components/LimitsOverview.vue'
import UbuntuOverview from './components/UbuntuOverview.vue'
import YouTubeGrowth from './components/YouTubeGrowth.vue'
import NetworkOverview from './components/NetworkOverview.vue'
import { useDashboard } from './composables/useDashboard'

const routes = [
  { id: 'home', label: 'Αρχική', short: 'Αρχική', icon: 'home', heading: 'home-title' },
  { id: 'week', label: 'Εβδομάδα και daily', short: 'Εβδομάδα', icon: 'week', heading: 'week-title' },
  { id: 'ubuntu', label: 'Σύστημα', short: 'Σύστημα', icon: 'system', heading: 'ubuntu-title' },
  { id: 'youtube', label: 'YouTube Growth', short: 'YouTube', icon: 'youtube', heading: 'youtube-title' },
  { id: 'network', label: 'Δίκτυο', short: 'Δίκτυο', icon: 'network', heading: 'network-title' },
  // The limits are always visible in the status bar; this page opens from there and is not in the rail.
  { id: 'usage', label: 'Όρια χρήσης', short: 'Όρια', icon: 'system', heading: 'limits-title', hidden: true },
]
const tabs = routes.filter(item => !item.hidden)
const pager = ref(null)
const active = ref('home')
const title = computed(() => routes.find(item => item.id === active.value)?.label ?? '')
// Late at night the board dims itself so an always-on tablet does not light the room.
const hour = ref(Number(new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Athens', hour: '2-digit', hour12: false }).format(new Date())))
const night = computed(() => hour.value >= 23 || hour.value < 7)
let hourTimer
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
  const hash = window.location.hash === '#standup' ? '#week' : window.location.hash
  const id = routes.find(menu => '#' + menu.id === hash)?.id ?? 'home'
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
  void navigate('week')
  standupRequest.value = request
}
function reportChanged() {
  void refreshReports(true)
}
onMounted(() => {
  hourTimer = setInterval(() => { hour.value = Number(new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/Athens', hour: '2-digit', hour12: false }).format(new Date())) }, 60000)
  route()
  window.addEventListener('resize', route)
  window.addEventListener('hashchange', route)
})
onUnmounted(() => {
  clearInterval(hourTimer)
  window.removeEventListener('hashchange', route)
  window.removeEventListener('resize', route)
})
</script>

<template>
  <v-app>
    <v-main tag="div" class="frame-main">
      <div class="frame" :class="{ night }">
        <AppRail :items="tabs" :active="active" @navigate="navigate" />
        <div class="stage">
          <StatusBar :title="title" :limits="limits" :loading="loading" @open="navigate('usage')" />
          <main ref="pager" class="pager" @scroll.passive="onScroll">
            <div class="pane pane-fit" role="tabpanel" aria-label="Αρχική"><div class="pane-inner">
              <HomeOverview :active="active === 'home'" :limits="limits" :loading="loading" :reports="reports"
                            @navigate="navigate" @standup="openStandup" />
            </div></div>
            <div class="pane pane-fit" role="tabpanel" aria-label="Εβδομάδα και daily"><div class="pane-inner">
              <StandupDraft :active="active === 'week'" :request="standupRequest" :reports="reports"
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
      </div>
    </v-main>
  </v-app>
</template>
